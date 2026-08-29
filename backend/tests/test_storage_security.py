"""Dedicated tests for the SSRF mitigation in app.services.storage and the
IDOR mitigation in app.schemas.broll.BrollInsertRequest.

Both were added by a security review that found:
  1. `download_from_url` could be pointed at cloud metadata / loopback /
     RFC1918 addresses (SSRF) -- mitigated by `_assert_public_http_url`,
     which resolves DNS and rejects private/loopback/link-local/reserved
     addresses, and is re-run on every redirect hop.
  2. `BrollInsertRequest.asset_url` could be a local filesystem path,
     which `video_render._resolve_local_broll_path` would then treat as a
     candidate local path -- letting a user composite another user's
     uploaded file into their own export (IDOR / cross-tenant file
     disclosure). Mitigated by a pydantic field_validator requiring
     http(s).
"""

from __future__ import annotations

import ipaddress
import socket

import httpx
import pytest
from fastapi import UploadFile
from pydantic import ValidationError

from app.exceptions import ValidationAppError
from app.schemas.broll import BrollInsertRequest
from app.services import storage as storage_module
from app.services.storage import _assert_public_http_url, download_from_url, save_upload

# ---------------------------------------------------------------------------
# _assert_public_http_url
# ---------------------------------------------------------------------------


class TestAssertPublicHttpUrl:
    def test_rejects_link_local_metadata_ip(self) -> None:
        # 169.254.169.254 -- the canonical cloud-metadata SSRF target.
        with pytest.raises(ValidationAppError):
            _assert_public_http_url("http://169.254.169.254/latest/meta-data/")

    def test_rejects_loopback_ip(self) -> None:
        with pytest.raises(ValidationAppError):
            _assert_public_http_url("http://127.0.0.1/")

    def test_rejects_loopback_hostname(self) -> None:
        with pytest.raises(ValidationAppError):
            _assert_public_http_url("http://localhost/")

    def test_rejects_private_10_range(self) -> None:
        with pytest.raises(ValidationAppError):
            _assert_public_http_url("http://10.0.0.1/video.mp4")

    def test_rejects_private_192_168_range(self) -> None:
        with pytest.raises(ValidationAppError):
            _assert_public_http_url("http://192.168.1.1/video.mp4")

    def test_rejects_private_172_16_range(self) -> None:
        with pytest.raises(ValidationAppError):
            _assert_public_http_url("http://172.16.0.1/video.mp4")

    def test_rejects_non_http_scheme(self) -> None:
        with pytest.raises(ValidationAppError):
            _assert_public_http_url("ftp://example.com/video.mp4")

    def test_rejects_file_scheme(self) -> None:
        with pytest.raises(ValidationAppError):
            _assert_public_http_url("file:///etc/passwd")

    def test_rejects_missing_host(self) -> None:
        with pytest.raises(ValidationAppError):
            _assert_public_http_url("http:///no-host-here")

    def test_rejects_unresolvable_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _raise_getaddrinfo(*args: object, **kwargs: object) -> None:
            raise OSError("Name or service not known")

        monkeypatch.setattr(socket, "getaddrinfo", _raise_getaddrinfo)
        with pytest.raises(ValidationAppError):
            _assert_public_http_url("http://this-does-not-resolve.example.invalid/video.mp4")

    def test_allows_public_looking_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock DNS resolution so this stays offline/deterministic: a
        hostname that resolves only to a public unicast address must be
        accepted (no exception raised)."""

        def _fake_getaddrinfo(host: str, port: object, *args: object, **kwargs: object):
            # 93.184.216.34 is a public, non-reserved IPv4 address.
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
        # Should not raise.
        _assert_public_http_url("https://cdn.example.com/video.mp4")

    def test_rejects_hostname_with_mixed_public_and_private_resolution(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A hostname resolving to *any* private address must be rejected
        even if it also resolves to a public one -- otherwise DNS rebinding
        could pick the private address on a later request."""

        def _fake_getaddrinfo(host: str, port: object, *args: object, **kwargs: object):
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0)),
            ]

        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
        with pytest.raises(ValidationAppError):
            _assert_public_http_url("https://rebinding.example.com/video.mp4")


# ---------------------------------------------------------------------------
# BrollInsertRequest.asset_url validation
# ---------------------------------------------------------------------------


def _valid_insert_kwargs(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "source": "pexels",
        "source_asset_id": "12345",
        "asset_url": "https://images.pexels.com/videos/12345/video.mp4",
        "keyword": "ocean",
        "position_start": 0.0,
        "position_end": 5.0,
    }
    kwargs.update(overrides)
    return kwargs


class TestBrollInsertRequestAssetUrlValidation:
    def test_https_url_is_accepted(self) -> None:
        request = BrollInsertRequest(**_valid_insert_kwargs())
        assert request.asset_url == "https://images.pexels.com/videos/12345/video.mp4"

    def test_http_url_is_accepted(self) -> None:
        request = BrollInsertRequest(
            **_valid_insert_kwargs(asset_url="http://images.pexels.com/videos/12345/video.mp4")
        )
        assert request.asset_url.startswith("http://")

    def test_absolute_local_path_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BrollInsertRequest(**_valid_insert_kwargs(asset_url="/etc/passwd"))

    def test_relative_traversal_path_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BrollInsertRequest(**_valid_insert_kwargs(asset_url="../../etc/passwd"))

    def test_another_users_upload_path_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BrollInsertRequest(
                **_valid_insert_kwargs(asset_url="uploads/videos/other-user-file.mp4")
            )

    def test_non_http_scheme_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BrollInsertRequest(**_valid_insert_kwargs(asset_url="file:///etc/passwd"))


# ---------------------------------------------------------------------------
# save_upload / download_from_url -- direct unit tests against the storage
# functions themselves (UPLOAD_ROOT is redirected to a per-test tmp dir by
# the autouse `_isolate_storage_paths` fixture in conftest.py).
# ---------------------------------------------------------------------------


def _make_upload_file(content: bytes, filename: str, content_type: str) -> UploadFile:
    import io

    from starlette.datastructures import Headers

    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


class TestSaveUpload:
    @pytest.mark.asyncio
    async def test_rejects_unsupported_content_type(self) -> None:
        upload = _make_upload_file(b"hello world", "notes.txt", "text/plain")
        with pytest.raises(ValidationAppError):
            await save_upload(upload, subdir="videos")

    @pytest.mark.asyncio
    async def test_saves_valid_video_and_cleans_up_on_oversize(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Shrink the size cap so a small fake payload trips the oversize
        # branch and its cleanup path, without needing a real multi-GB file.
        monkeypatch.setattr(storage_module, "MAX_UPLOAD_SIZE_BYTES", 5)
        monkeypatch.setattr(storage_module, "_CHUNK_SIZE", 1)
        upload = _make_upload_file(b"this is more than five bytes", "clip.mp4", "video/mp4")
        with pytest.raises(ValidationAppError):
            await save_upload(upload, subdir="videos")

        # The partially-written file must not be left behind.
        leftover = list((storage_module.UPLOAD_ROOT / "videos").glob("*.mp4"))
        assert leftover == []

    @pytest.mark.asyncio
    async def test_saves_valid_video_successfully(self) -> None:
        upload = _make_upload_file(b"fake mp4 bytes", "clip.mp4", "video/mp4")
        relative_path = await save_upload(upload, subdir="videos")
        assert relative_path.startswith("videos/")
        assert relative_path.endswith(".mp4")
        assert (storage_module.UPLOAD_ROOT / relative_path).read_bytes() == b"fake mp4 bytes"


class _FakeStreamResponse:
    """Minimal stand-in for the subset of httpx.Response used by
    download_from_url's manual streaming/redirect loop."""

    def __init__(
        self,
        *,
        url: str,
        is_redirect: bool = False,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> None:
        self.url = httpx.URL(url)
        self.is_redirect = is_redirect
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body

    async def aiter_bytes(self, chunk_size: int):  # noqa: ANN201
        yield self._body


class _FakeStreamCtx:
    def __init__(self, response: _FakeStreamResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeStreamResponse:
        return self._response

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


def _fake_getaddrinfo_host_aware(host: str, *args: object, **kwargs: object):
    """A deterministic, offline stand-in for socket.getaddrinfo: resolves an
    IP-literal host to itself (so private/reserved IP-literal targets, e.g.
    a redirect Location header, are still correctly flagged) and any other
    hostname to a fixed public IP."""

    try:
        ipaddress.ip_address(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, 0))]
    except ValueError:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


def _patch_stream_sequence(
    monkeypatch: pytest.MonkeyPatch, responses: list[_FakeStreamResponse]
) -> None:
    """Patch httpx.AsyncClient.stream to return each response in `responses`
    in turn (one per call), mimicking download_from_url's manual redirect
    loop without any real network access."""

    iterator = iter(responses)

    def fake_stream(self: httpx.AsyncClient, method: str, url: str, **kwargs: object):
        return _FakeStreamCtx(next(iterator))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)


class TestDownloadFromUrl:
    @pytest.mark.asyncio
    async def test_downloads_video_successfully(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_stream_sequence(
            monkeypatch,
            [
                _FakeStreamResponse(
                    url="https://cdn.example.com/video.mp4",
                    headers={"content-type": "video/mp4"},
                    body=b"fake video content",
                )
            ],
        )
        monkeypatch.setattr(storage_module.socket, "getaddrinfo", _fake_getaddrinfo_host_aware)

        relative_path = await download_from_url(
            "https://cdn.example.com/video.mp4", subdir="videos"
        )
        assert relative_path.startswith("videos/")
        saved = storage_module.UPLOAD_ROOT / relative_path
        assert saved.read_bytes() == b"fake video content"

    @pytest.mark.asyncio
    async def test_rejects_non_video_content_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_stream_sequence(
            monkeypatch,
            [
                _FakeStreamResponse(
                    url="https://cdn.example.com/notavideo",
                    headers={"content-type": "text/html"},
                    body=b"<html></html>",
                )
            ],
        )
        monkeypatch.setattr(storage_module.socket, "getaddrinfo", _fake_getaddrinfo_host_aware)

        with pytest.raises(ValidationAppError):
            await download_from_url("https://cdn.example.com/notavideo", subdir="videos")

    @pytest.mark.asyncio
    async def test_redirect_target_is_revalidated_and_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A public-looking URL that 302s to a private address must be
        rejected -- the whole point of re-running _assert_public_http_url
        on every redirect hop, not just the original URL."""

        _patch_stream_sequence(
            monkeypatch,
            [
                _FakeStreamResponse(
                    url="https://public.example.com/redirect",
                    is_redirect=True,
                    status_code=302,
                    headers={"location": "http://169.254.169.254/secret"},
                )
            ],
        )
        monkeypatch.setattr(storage_module.socket, "getaddrinfo", _fake_getaddrinfo_host_aware)

        with pytest.raises(ValidationAppError):
            await download_from_url("https://public.example.com/redirect", subdir="videos")

    @pytest.mark.asyncio
    async def test_http_error_status_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_stream_sequence(
            monkeypatch,
            [
                _FakeStreamResponse(
                    url="https://cdn.example.com/gone.mp4",
                    status_code=404,
                )
            ],
        )
        monkeypatch.setattr(storage_module.socket, "getaddrinfo", _fake_getaddrinfo_host_aware)

        with pytest.raises(ValidationAppError):
            await download_from_url("https://cdn.example.com/gone.mp4", subdir="videos")
