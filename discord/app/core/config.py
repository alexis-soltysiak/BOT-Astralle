from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "local"
    log_level: str = "INFO"

    discord_token: str = ""
    discord_application_id: int
    backend_base_url: str = "http://localhost:8000"
    backend_proxy_secret: str = ""
    discord_service_token: str = ""

    discord_consumer_id: str = "discord-bot-dev"
    publish_poll_interval_seconds: int = 5
    live_refresh_interval_seconds: int = 60

    discord_matches_channel_id: int | None = None
    discord_leaderboard_channel_id: int | None = None
    discord_live_channel_id: int | None = None
    discord_finished_channel_id: int | None = None

    discord_guild_id: int | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
