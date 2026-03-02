from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RankedSnapshot(Base):
    __tablename__ = "ranked_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tracked_player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracked_player.id", ondelete="CASCADE"), nullable=False
    )

    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    summoner_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    queue_type: Mapped[str] = mapped_column(String(32), nullable=False)

    tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    division: Mapped[str | None] = mapped_column(String(8), nullable=True)
    league_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    losses: Mapped[int | None] = mapped_column(Integer, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )