from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from .models import DiscordBindingKey, LeaderboardMode


class BindingUpsertIn(BaseModel):
    guild_id: str = Field(min_length=1)
    channel_id: str = Field(min_length=1)
    message_id: str | None = None
    leaderboard_mode: LeaderboardMode | None = None
    is_enabled: bool = True
    last_error: str | None = None


class BindingPatchIn(BaseModel):
    channel_id: str | None = None
    message_id: str | None = None
    leaderboard_mode: LeaderboardMode | None = None
    is_enabled: bool | None = None
    last_error: str | None = None


class BindingOut(BaseModel):
    id: int
    guild_id: str
    binding_key: DiscordBindingKey
    channel_id: str
    message_id: str | None
    leaderboard_mode: LeaderboardMode | None
    is_enabled: bool
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}