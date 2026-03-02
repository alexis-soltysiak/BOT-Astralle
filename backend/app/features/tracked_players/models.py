from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TrackedPlayer(Base):
    __tablename__ = "tracked_player"
    __table_args__ = (
        UniqueConstraint("region", "game_name", "tag_line", name="uq_tracked_player_riot_id"),
        UniqueConstraint("puuid", name="uq_tracked_player_puuid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    region: Mapped[str] = mapped_column(String(16), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(16), nullable=True)
    discord_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    discord_display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    game_name: Mapped[str] = mapped_column(String(64), nullable=False)
    tag_line: Mapped[str] = mapped_column(String(16), nullable=False)

    puuid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
