"""Application configuration.

Settings are loaded from environment variables (and a local .env file in
development). See the repository root README / .env.example for the full
list of variables expected in each environment.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    NOTE: SECRET_KEY has no safe default and MUST be provided via the
    environment (or a .env file) in every environment, including local
    development. Never hardcode a real secret here.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "VideoToShorts"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Database (owned by DATABASE-AGENT; referenced here only)
    DATABASE_URL: str

    # Auth / JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # Third-party media APIs (B-roll)
    PEXELS_API_KEY: str = ""
    PIXABAY_API_KEY: str = ""

    # OpenAI API key for text-to-shorts script generation.
    # Leave empty to use the built-in heuristic fallback (no AI key needed).
    OPENAI_API_KEY: str = ""


    # Transcription. `auto` uses the hosted Whisper API when
    # TRANSCRIPTION_API_KEY is set and local Whisper otherwise, so the app
    # transcribes for real out of the box with nothing to configure;
    # `local` and `api` force one or the other.
    TRANSCRIPTION_BACKEND: str = "auto"
    TRANSCRIPTION_API_KEY: str = ""
    # Local Whisper (faster-whisper). `base` transcribes about 10x faster
    # than realtime on a laptop CPU and is accurate enough to pick
    # highlights and caption them; `small`/`medium` are better and slower.
    # The model downloads once, on first use, into the HuggingFace cache.
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "auto"
    WHISPER_COMPUTE_TYPE: str = "int8"
    # Fixing the language skips detection and stops a quiet opening from
    # being mistaken for another one. Empty means detect per video.
    WHISPER_LANGUAGE: str = ""

    # Object storage (uploaded videos, generated clips, exports)
    STORAGE_BUCKET: str = ""
    STORAGE_ACCESS_KEY: str = ""
    STORAGE_SECRET_KEY: str = ""

    # Background task queue (RQ + Redis). Leave unset to run jobs via
    # FastAPI's own BackgroundTasks instead (default; always the case in
    # tests, which don't want a real Redis dependency).
    REDIS_URL: str = ""

    # ---- Render / export quality -------------------------------------
    # Defaults follow YouTube's recommended Shorts upload spec so an
    # exported clip can be uploaded without a lossy re-encode round trip.
    # Consumed by app.services.video_render.
    RENDER_WIDTH: int = 1080
    RENDER_HEIGHT: int = 1920
    RENDER_FPS: int = 30
    # x264 constant-rate-factor: lower = higher quality/larger file.
    # 18 is visually transparent for short-form; 20-23 is fine for drafts.
    RENDER_CRF: int = 18
    RENDER_PRESET: str = "slow"
    # How a non-9:16 source is fitted:
    #   "auto"  - track the speaker and crop the frame around them (default)
    #   "blur"  - fit the whole frame over a blurred fill
    #   "crop"  - centre-crop to fill (ignores where the subject actually is)
    #   "pad"   - plain black letterbox
    RENDER_FRAMING: str = "auto"
    RENDER_BLUR_SIGMA: int = 30
    # Source B-roll automatically when a clip is exported with none
    # attached. The inserted assets stay editable/removable in the clip
    # editor, per the B-roll module's rules.
    BROLL_AUTO_ON_EXPORT: bool = True
    # Sizing for the "bottom_right" BrollPlacement's PIP card. Other
    # placements (top/bottom/split) size themselves from RENDER_HEIGHT
    # directly -- see app.services.video_render._apply_broll.
    RENDER_PIP_WIDTH_RATIO: float = 0.33
    # Caption font size and bottom margin, as a fraction of frame height.
    # The margin keeps captions clear of the YouTube Shorts UI overlay.
    RENDER_CAPTION_SCALE: float = 0.036
    RENDER_CAPTION_MARGIN_RATIO: float = 0.17
    RENDER_CAPTION_FONT: str = "DejaVu Sans"
    # Short-form captions are often set in caps; off by default because
    # sentence case reads better for long-form speech.
    RENDER_CAPTION_UPPERCASE: bool = False
    # Optional explicit font file for the drawtext caption fallback; when
    # empty a known system font is auto-detected.
    RENDER_CAPTION_FONT_FILE: str = ""
    RENDER_AUDIO_BITRATE: str = "192k"
    # YouTube normalises playback to roughly -14 LUFS.
    RENDER_AUDIO_LUFS: float = -14.0


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Cached via lru_cache so environment variables are only parsed once per
    process; use `get_settings.cache_clear()` in tests if env vars change
    between test cases.
    """

    return Settings()


settings = get_settings()
