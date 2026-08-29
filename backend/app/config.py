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
    ]

    # Third-party media APIs (B-roll)
    PEXELS_API_KEY: str = ""
    PIXABAY_API_KEY: str = ""

    # Transcription provider
    TRANSCRIPTION_API_KEY: str = ""

    # Object storage (uploaded videos, generated clips, exports)
    STORAGE_BUCKET: str = ""
    STORAGE_ACCESS_KEY: str = ""
    STORAGE_SECRET_KEY: str = ""

    # Background task queue (RQ + Redis). Leave unset to run jobs via
    # FastAPI's own BackgroundTasks instead (default; always the case in
    # tests, which don't want a real Redis dependency).
    REDIS_URL: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Cached via lru_cache so environment variables are only parsed once per
    process; use `get_settings.cache_clear()` in tests if env vars change
    between test cases.
    """

    return Settings()


settings = get_settings()
