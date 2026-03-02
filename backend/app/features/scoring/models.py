from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MatchScore(Base):
    __tablename__ = "match_score"
    __table_args__ = (UniqueConstraint("match_id", "puuid", name="uq_match_score_match_puuid"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("match.id", ondelete="CASCADE"), nullable=False
    )

    puuid: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)

    final_score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    final_grade: Mapped[str] = mapped_column(String(4), nullable=False)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())