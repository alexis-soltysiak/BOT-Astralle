from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.tracked_players.models import TrackedPlayer


class TrackedPlayersRepository:
    async def get_all(self, session: AsyncSession) -> list[TrackedPlayer]:
        res = await session.execute(select(TrackedPlayer).order_by(TrackedPlayer.created_at.desc()))
        return list(res.scalars().all())

    async def get_by_id(self, session: AsyncSession, player_id: uuid.UUID) -> TrackedPlayer | None:
        res = await session.execute(select(TrackedPlayer).where(TrackedPlayer.id == player_id))
        return res.scalar_one_or_none()

    async def get_by_riot_id(
        self, session: AsyncSession, region: str, game_name: str, tag_line: str
    ) -> TrackedPlayer | None:
        stmt = select(TrackedPlayer).where(
            TrackedPlayer.region == region,
            TrackedPlayer.game_name == game_name,
            TrackedPlayer.tag_line == tag_line,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_puuid(self, session: AsyncSession, puuid: str) -> TrackedPlayer | None:
        res = await session.execute(select(TrackedPlayer).where(TrackedPlayer.puuid == puuid))
        return res.scalar_one_or_none()

    async def create(self, session: AsyncSession, player: TrackedPlayer) -> TrackedPlayer:
        session.add(player)
        await session.commit()
        await session.refresh(player)
        return player

    async def set_active(
        self, session: AsyncSession, player: TrackedPlayer, active: bool
    ) -> TrackedPlayer:
        player.active = active
        await session.commit()
        await session.refresh(player)
        return player

    async def delete(self, session: AsyncSession, player_id: uuid.UUID) -> None:
        await session.execute(delete(TrackedPlayer).where(TrackedPlayer.id == player_id))
        await session.commit()