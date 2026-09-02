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

    discord_leaderboard_channel_id: int | None = None
    discord_live_channel_id: int | None = None
    discord_finished_channel_id: int | None = None

    discord_guild_id: int | None = None

    llm_match_analysis_enabled: bool = True
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: float = 12.0

    lisnard_enabled: bool = True
    lisnard_model: str = "gpt-5.6"
    lisnard_history_limit: int = 25
    lisnard_timeout_seconds: float = 120.0
    lisnard_web_search_enabled: bool = True
    lisnard_max_output_tokens: int = 32000
    lisnard_reasoning_effort: str = "low"


@lru_cache
def get_settings() -> Settings:
    return Settings()
