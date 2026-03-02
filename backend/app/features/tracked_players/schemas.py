from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.features.tracked_players.validators import (
    normalize_discord_display_name,
    normalize_discord_user_id,
    normalize_game_name,
    normalize_tag_line,
    validate_platform,
    validate_region,
)


class TrackedPlayerCreate(BaseModel):
    discord_user_id: str = Field(min_length=1, max_length=32)
    discord_display_name: str | None = Field(default=None, max_length=64)
    game_name: str = Field(min_length=1, max_length=64)
    tag_line: str = Field(min_length=1, max_length=16)
    region: str = Field(default="europe")
    platform: str | None = None
    puuid: str | None = None
    active: bool = True

    @field_validator("discord_user_id")
    @classmethod
    def _vn_discord_user_id(cls, v: str) -> str:
        return normalize_discord_user_id(v)

    @field_validator("discord_display_name")
    @classmethod
    def _vn_discord_display_name(cls, v: str | None) -> str | None:
        return normalize_discord_display_name(v)

    @field_validator("game_name")
    @classmethod
    def _vn_gn(cls, v: str) -> str:
        return normalize_game_name(v)

    @field_validator("tag_line")
    @classmethod
    def _vn_tl(cls, v: str) -> str:
        return normalize_tag_line(v)

    @field_validator("region")
    @classmethod
    def _vn_region(cls, v: str) -> str:
        return validate_region(v)

    @field_validator("platform")
    @classmethod
    def _vn_platform(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_platform(v)


class TrackedPlayerPatch(BaseModel):
    active: bool | None = None
    platform: str | None = None
    discord_user_id: str | None = Field(default=None, max_length=32)
    discord_display_name: str | None = Field(default=None, max_length=64)

    @field_validator("discord_user_id")
    @classmethod
    def _vn_discord_user_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return normalize_discord_user_id(v)

    @field_validator("discord_display_name")
    @classmethod
    def _vn_discord_display_name(cls, v: str | None) -> str | None:
        return normalize_discord_display_name(v)

    @field_validator("platform")
    @classmethod
    def _vn_platform(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_platform(v)


class TrackedPlayerOut(BaseModel):
    id: uuid.UUID
    region: str
    platform: str | None
    discord_user_id: str | None
    discord_display_name: str | None
    game_name: str
    tag_line: str
    puuid: str | None
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
