from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.matches.models import Match, MatchParticipant


class MatchesRepository:
    async def exists(self, session: AsyncSession, riot_match_id: str) -> bool:
        res = await session.execute(select(Match.id).where(Match.riot_match_id == riot_match_id))
        return res.first() is not None

    async def list_matches(self, session: AsyncSession, limit: int) -> list[Match]:
        res = await session.execute(select(Match).order_by(Match.created_at.desc()).limit(limit))
        return list(res.scalars().all())

    async def get_by_riot_id(self, session: AsyncSession, riot_match_id: str) -> Match | None:
        res = await session.execute(select(Match).where(Match.riot_match_id == riot_match_id))
        return res.scalar_one_or_none()

    async def list_participants(self, session: AsyncSession, match_id: uuid.UUID) -> list[MatchParticipant]:
        res = await session.execute(
            select(MatchParticipant).where(MatchParticipant.match_id == match_id)
        )
        return list(res.scalars().all())

    async def list_matches_by_participant_puuid(self, session: AsyncSession, puuid: str) -> list[Match]:
        stmt = (
            select(Match)
            .join(MatchParticipant, MatchParticipant.match_id == Match.id)
            .where(MatchParticipant.puuid == puuid)
            .order_by(Match.created_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def delete_matches(self, session: AsyncSession, match_ids: list[uuid.UUID]) -> None:
        if not match_ids:
            return
        await session.execute(delete(Match).where(Match.id.in_(match_ids)))
        await session.commit()
