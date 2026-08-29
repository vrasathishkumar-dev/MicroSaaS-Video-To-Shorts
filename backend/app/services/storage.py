"""Local-disk file storage abstraction for uploaded videos and related assets.

Everything lives under UPLOAD_ROOT (backend/uploads/). `save_upload()` /
`download_from_url()` return a path relative to UPLOAD_ROOT (a "key"),
suitable for persisting on a model and later resolving back to an absolute
path via `get_file_path()`.
"""

import asyncio
import ipaddress
import logging
import socket
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import UploadFile

try:
    import yt_dlp
except ImportError:
    yt_dlp = None  # type: ignore[assignment]

from app.exceptions import ValidationAppError

logger = logging.getLogger(__name__)

# Root directory backing local storage. Relative paths returned by
# save_upload() are relative to this directory. Resolves to backend/uploads/.
UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "uploads"

# Video content-types accepted for upload.
ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "video/webm",
    "video/mpeg",
}

MAX_UPLOAD_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2GB
_CHUNK_SIZE = 1024 * 1024  # 1MB, streamed to avoid buffering the whole file in memory

_WEB_VIDEO_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "tiktok.com",
    "dailymotion.com",
    "twitch.tv",
    "facebook.com",
    "fb.watch",
    "instagram.com",
    "twitter.com",
    "x.com",
)


def _is_web_video_url(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return any(domain in hostname for domain in _WEB_VIDEO_DOMAINS)


def _download_via_ytdlp(url: str, target_dir: Path, filename_stem: str) -> Path:
    """Download video using yt-dlp for video platforms, merging video and audio streams."""
    if yt_dlp is None:
        raise ValidationAppError("yt-dlp is not installed")
    outtmpl = str(target_dir / f"{filename_stem}.%(ext)s")
    ydl_opts = {
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080][ext=mp4]/best",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": MAX_UPLOAD_SIZE_BYTES,
        "socket_timeout": 30,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            actual_path = Path(ydl.prepare_filename(info))
            if not actual_path.exists():
                candidates = list(target_dir.glob(f"{filename_stem}.*"))
                if candidates:
                    return candidates[0]
                raise ValidationAppError("yt-dlp downloaded file not found")
            return actual_path
    except Exception as exc:
        for partial in target_dir.glob(f"{filename_stem}.*"):
            try:
                partial.unlink(missing_ok=True)
            except Exception:
                pass
        err_msg = str(exc)
        if "No space left on device" in err_msg or "Errno 28" in err_msg:
            raise ValidationAppError(
                "Device ran out of storage space while downloading this video. Please free up some disk space."
            ) from exc
        raise


async def save_upload(file: UploadFile, subdir: str) -> str:
    """Validate and persist an uploaded video file under uploads/<subdir>/.

    The file is streamed to disk in chunks under a generated UUID filename
    (preserving the original extension when present), so large uploads never
    need to be fully buffered in memory.

    Returns the path relative to UPLOAD_ROOT (e.g. "videos/<uuid>.mp4"),
    suitable for persisting on a model (e.g. VideoProject.source_file_path)
    and later resolving back to an absolute path via get_file_path().

    Raises:
        ValidationAppError: if `file.content_type` is not a supported video
            type, or the file exceeds MAX_UPLOAD_SIZE_BYTES.
    """
    if file.content_type not in ALLOWED_VIDEO_CONTENT_TYPES:
        raise ValidationAppError(
            f"Unsupported file type '{file.content_type}'. Expected a video file."
        )

    suffix = Path(file.filename or "").suffix or ".mp4"
    filename = f"{uuid.uuid4().hex}{suffix}"

    target_dir = UPLOAD_ROOT / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename

    size = 0
    try:
        with target_path.open("wb") as out_file:
            while chunk := await file.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE_BYTES:
                    raise ValidationAppError(
                        "File exceeds maximum allowed size of "
                        f"{MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB."
                    )
                out_file.write(chunk)
    except ValidationAppError:
        target_path.unlink(missing_ok=True)
        raise
    except Exception:
        target_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    logger.info("Saved upload to %s (%d bytes)", target_path, size)
    return str(Path(subdir) / filename)


_MAX_REDIRECTS = 5


def _assert_public_http_url(url: str) -> None:
    """Reject a URL that isn't a safe, public http(s) target.

    Mitigates SSRF: `download_from_url` fetches a URL supplied by an
    authenticated user from a background task with no request-scoped
    caller to bound the blast radius. Without this check, a user could
    point `source_url` at cloud metadata endpoints (169.254.169.254),
    loopback, or other RFC1918/internal addresses and have the server make
    the request on their behalf. Every hostname this resolves to must be a
    public, non-reserved address — resolving *any* private/loopback/
    link-local/multicast/reserved address is enough to reject the whole
    URL (a hostname resolving to multiple IPs, only some private, is still
    rejected — DNS rebinding could otherwise pick the private one later).

    Raises:
        ValidationAppError: if the scheme isn't http(s), the host is
            missing, DNS resolution fails, or any resolved address is not
            a public unicast address.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValidationAppError("source_url must be an http(s) URL")
    if not parsed.hostname:
        raise ValidationAppError("source_url is missing a host")

    try:
        addrinfo = socket.getaddrinfo(parsed.hostname, None)
    except OSError as exc:
        raise ValidationAppError(f"Could not resolve source_url host: {exc}") from exc

    for _family, _type, _proto, _canonname, sockaddr in addrinfo:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValidationAppError(
                "source_url resolves to a non-public address and cannot be fetched"
            )


async def download_from_url(url: str, subdir: str) -> str:
    """Download a source video from a URL and persist it under uploads/<subdir>/.

    For video platforms (YouTube, Vimeo, TikTok, etc.), uses yt-dlp to extract
    and download the best available MP4 video. For direct video URLs, streams
    the response to disk in chunks. Enforces SSRF safety and size limits.

    Returns the path relative to UPLOAD_ROOT, same convention as save_upload().

    Raises:
        ValidationAppError: if the URL isn't a safe public http(s) target,
            can't be fetched, isn't a video, or exceeds MAX_UPLOAD_SIZE_BYTES.
    """
    await asyncio.to_thread(_assert_public_http_url, url)

    target_dir = UPLOAD_ROOT / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex

    if _is_web_video_url(url) and yt_dlp is not None:
        try:
            downloaded_path = await asyncio.to_thread(
                _download_via_ytdlp, url, target_dir, file_id
            )
            return str(Path(subdir) / downloaded_path.name)
        except Exception as exc:
            logger.error("yt-dlp failed to download %s: %s", url, exc)
            raise ValidationAppError(f"Could not download video from URL: {exc}") from exc

    suffix = Path(urlparse(url).path).suffix or ".mp4"
    filename = f"{file_id}{suffix}"
    target_path = target_dir / filename

    size = 0
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=False) as client:
            current_url = url
            for _ in range(_MAX_REDIRECTS + 1):
                async with client.stream("GET", current_url) as response:
                    if response.is_redirect:
                        next_url = response.headers.get("location")
                        if not next_url:
                            raise ValidationAppError("Redirect response missing Location header")
                        current_url = str(response.url.join(next_url))
                        await asyncio.to_thread(_assert_public_http_url, current_url)
                        continue

                    if response.status_code >= 400:
                        raise ValidationAppError(
                            f"Could not download source video (HTTP {response.status_code})."
                        )
                    content_type = response.headers.get("content-type", "")
                    if not content_type.startswith("video/"):
                        if yt_dlp is not None:
                            try:
                                downloaded_path = await asyncio.to_thread(
                                    _download_via_ytdlp, url, target_dir, file_id
                                )
                                return str(Path(subdir) / downloaded_path.name)
                            except Exception:
                                pass
                        raise ValidationAppError(
                            f"URL did not return a video (content-type: {content_type!r})."
                        )
                    with target_path.open("wb") as out_file:
                        async for chunk in response.aiter_bytes(_CHUNK_SIZE):
                            size += len(chunk)
                            if size > MAX_UPLOAD_SIZE_BYTES:
                                raise ValidationAppError(
                                    "Downloaded file exceeds maximum allowed size of "
                                    f"{MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB."
                                )
                            out_file.write(chunk)
                    break
            else:
                raise ValidationAppError("Too many redirects while fetching source_url")

        if size == 0:
            raise ValidationAppError("Downloaded file is empty.")
    except ValidationAppError:
        target_path.unlink(missing_ok=True)
        raise
    except httpx.HTTPError as exc:
        target_path.unlink(missing_ok=True)
        raise ValidationAppError(f"Could not download source video: {exc}") from exc
    except Exception:
        target_path.unlink(missing_ok=True)
        raise

    logger.info("Downloaded %s to %s (%d bytes)", url, target_path, size)
    return str(Path(subdir) / filename)


def get_file_path(relative_path: str) -> Path:
    """Resolve a relative path (as returned by save_upload()) to an absolute Path."""

    return UPLOAD_ROOT / relative_path
