from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
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

    # Les alias LISNARD_* sont conserves pour ne pas casser les .env deja
    # deployes, qui datent d'avant l'ajout d'un second personnage.
    persona_enabled: bool = Field(
        True, validation_alias=AliasChoices("PERSONA_ENABLED", "LISNARD_ENABLED")
    )
    persona_model: str = Field(
        "gpt-5.6-terra", validation_alias=AliasChoices("PERSONA_MODEL", "LISNARD_MODEL")
    )
    persona_history_limit: int = Field(
        25, validation_alias=AliasChoices("PERSONA_HISTORY_LIMIT", "LISNARD_HISTORY_LIMIT")
    )
    persona_timeout_seconds: float = Field(
        120.0, validation_alias=AliasChoices("PERSONA_TIMEOUT_SECONDS", "LISNARD_TIMEOUT_SECONDS")
    )
    persona_web_search_enabled: bool = Field(
        True,
        validation_alias=AliasChoices("PERSONA_WEB_SEARCH_ENABLED", "LISNARD_WEB_SEARCH_ENABLED"),
    )
    persona_max_output_tokens: int = Field(
        32000,
        validation_alias=AliasChoices("PERSONA_MAX_OUTPUT_TOKENS", "LISNARD_MAX_OUTPUT_TOKENS"),
    )
    persona_reasoning_effort: str = Field(
        "low", validation_alias=AliasChoices("PERSONA_REASONING_EFFORT", "LISNARD_REASONING_EFFORT")
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
