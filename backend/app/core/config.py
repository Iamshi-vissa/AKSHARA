"""Application settings.

All configuration comes from environment variables prefixed ``AKSHARA_`` (or a local
``.env`` file in development). Secrets are never given defaults: the app refuses to start
without them. See ``.env.example`` at the repository root for every option.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AKSHARA_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # --- Database / broker -------------------------------------------------------------
    database_url: str = Field(
        description="SQLAlchemy async URL, e.g. postgresql+asyncpg://user:pass@host/db"
    )
    redis_url: str = "redis://localhost:6379/0"

    # --- Security ----------------------------------------------------------------------
    jwt_secret: SecretStr = Field(description="HMAC secret for access tokens, >= 32 chars")
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_seconds: int = 14 * 24 * 3600
    cookie_secure: bool = True
    login_rate_limit_per_minute: int = 10
    rate_limit_backend: Literal["redis", "memory"] = "redis"

    # --- Storage -----------------------------------------------------------------------
    storage_backend: Literal["local"] = "local"
    storage_root: Path = Path("./var/blobs")

    # --- Upload limits (decision D15) ---------------------------------------------------
    max_upload_bytes: int = 50 * 1024 * 1024
    max_ooxml_uncompressed_bytes: int = 200 * 1024 * 1024
    max_ooxml_entries: int = 10_000
    max_compression_ratio: int = 100

    @field_validator("jwt_secret")
    @classmethod
    def _secret_strength(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 32:
            raise ValueError("AKSHARA_JWT_SECRET must be at least 32 characters")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from the environment
