from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DiscordBindingKey(str, enum.Enum):
    LEADERBOARD_MESSAGE = "LEADERBOARD_MESSAGE"
    LIVE_GAMES_MESSAGE = "LIVE_GAMES_MESSAGE"
    FINISHED_GAMES_CHANNEL = "FINISHED_GAMES_CHANNEL"


class LeaderboardMode(str, enum.Enum):
    solo = "solo"
    flex = "flex"


class DiscordMessageBinding(Base):
    __tablename__ = "discord_message_binding"
    __table_args__ = (UniqueConstraint("guild_id", "binding_key", name="uq_discord_binding_guild_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    binding_key: Mapped[DiscordBindingKey] = mapped_column(Enum(DiscordBindingKey), nullable=False)

    channel_id: Mapped[str] = mapped_column(String(32), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    leaderboard_mode: Mapped[LeaderboardMode | None] = mapped_column(Enum(LeaderboardMode), nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
