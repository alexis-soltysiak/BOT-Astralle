from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Match(Base):
    __tablename__ = "match"
    __table_args__ = (UniqueConstraint("riot_match_id", name="uq_match_riot_match_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    riot_match_id: Mapped[str] = mapped_column(String(32), nullable=False)
    region: Mapped[str] = mapped_column(String(16), nullable=False)

    queue_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    game_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)

    game_start_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    game_end_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    game_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MatchParticipant(Base):
    __tablename__ = "match_participant"
    __table_args__ = (UniqueConstraint("match_id", "puuid", name="uq_match_participant_match_puuid"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("match.id", ondelete="CASCADE"), nullable=False
    )

    puuid: Mapped[str] = mapped_column(String(128), nullable=False)
    team_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    riot_id_game_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    riot_id_tag_line: Mapped[str | None] = mapped_column(String(16), nullable=True)

    champion_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    kills: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deaths: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assists: Mapped[int | None] = mapped_column(Integer, nullable=True)

    win: Mapped[bool | None] = mapped_column(nullable=True)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)