from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.live_games.models import LiveGameRankedSnapshot, LiveGameState


class LiveGamesRepository:
    async def get_by_player_id(
        self, session: AsyncSession, tracked_player_id: uuid.UUID
    ) -> LiveGameState | None:
        res = await session.execute(
            select(LiveGameState).where(LiveGameState.tracked_player_id == tracked_player_id)
        )
        return res.scalar_one_or_none()

    async def upsert_state(
        self,
        session: AsyncSession,
        tracked_player_id: uuid.UUID,
        platform: str | None,
        status: str,
        game_id: str | None,
        payload: dict | None,
    ) -> None:
        fetched_at = datetime.now(timezone.utc)
        row = await self.get_by_player_id(session, tracked_player_id)
        if row is None:
            row = LiveGameState(
                tracked_player_id=tracked_player_id,
                platform=platform,
                status=status,
                game_id=game_id,
                payload=payload,
                fetched_at=fetched_at,
            )
            session.add(row)
            await session.commit()
            return

        row.platform = platform
        row.status = status
        row.game_id = game_id
        row.payload = payload
        row.fetched_at = fetched_at
        await session.commit()

    async def list_states(self, session: AsyncSession) -> list[LiveGameState]:
        res = await session.execute(select(LiveGameState))
        return list(res.scalars().all())

    async def get_ranked_snapshot(
        self,
        session: AsyncSession,
        tracked_player_id: uuid.UUID,
        game_id: str,
        queue_type: str,
    ) -> LiveGameRankedSnapshot | None:
        res = await session.execute(
            select(LiveGameRankedSnapshot).where(
                LiveGameRankedSnapshot.tracked_player_id == tracked_player_id,
                LiveGameRankedSnapshot.game_id == game_id,
                LiveGameRankedSnapshot.queue_type == queue_type,
            )
        )
        return res.scalar_one_or_none()

    async def upsert_ranked_snapshot(
        self,
        session: AsyncSession,
        *,
        tracked_player_id: uuid.UUID,
        platform: str | None,
        game_id: str,
        queue_type: str,
        tier: str | None,
        division: str | None,
        league_points: int | None,
        wins: int | None,
        losses: int | None,
    ) -> None:
        fetched_at = datetime.now(timezone.utc)
        row = await self.get_ranked_snapshot(session, tracked_player_id, game_id, queue_type)
        if row is None:
            row = LiveGameRankedSnapshot(
                tracked_player_id=tracked_player_id,
                platform=platform,
                game_id=game_id,
                queue_type=queue_type,
                tier=tier,
                division=division,
                league_points=league_points,
                wins=wins,
                losses=losses,
                fetched_at=fetched_at,
            )
            session.add(row)
            await session.commit()
            return

        row.platform = platform
        row.tier = tier
        row.division = division
        row.league_points = league_points
        row.wins = wins
        row.losses = losses
        row.fetched_at = fetched_at
        await session.commit()
