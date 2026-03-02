from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LiveGameState(Base):
    __tablename__ = "live_game_state"
    __table_args__ = (UniqueConstraint("tracked_player_id", name="uq_live_game_state_player"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tracked_player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracked_player.id", ondelete="CASCADE"), nullable=False
    )

    platform: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    game_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )