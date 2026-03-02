from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    env: str = "local"
    log_level: str = "INFO"

    discord_token: str = ""
    discord_application_id: str = ""

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/app"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    cors_allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    backend_proxy_secret: str = ""
    discord_service_token: str = ""
    admin_username: str = ""
    admin_password: str = ""
    admin_session_secret: str = ""
    admin_session_ttl_seconds: int = 60 * 60 * 12
    admin_session_cookie_name: str = "astralle_admin_session"

    riot_api_key: str = ""

    scheduler_enabled: bool = True

    matches_ingest_count: int = 10

    publication_lease_seconds: int = 90
    publication_max_attempts: int = 10

    discord_leaderboard_channel_id: int | None = None
    discord_finished_channel_id: int | None = None

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        raw = value.strip()
        if not raw:
            return []

        if raw.startswith("["):
            import json

            return json.loads(raw)

        return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
