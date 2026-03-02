from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.leaderboards.models import RankedSnapshot


class LeaderboardsRepository:
    async def insert_snapshots(self, session: AsyncSession, snapshots: list[RankedSnapshot]) -> None:
        if not snapshots:
            return
        session.add_all(snapshots)
        await session.commit()

    async def get_latest_snapshots(self, session: AsyncSession) -> list[RankedSnapshot]:
        sub = (
            select(
                RankedSnapshot.tracked_player_id.label("tracked_player_id"),
                RankedSnapshot.queue_type.label("queue_type"),
                func.max(RankedSnapshot.fetched_at).label("mx"),
            )
            .group_by(RankedSnapshot.tracked_player_id, RankedSnapshot.queue_type)
            .subquery()
        )

        stmt = (
            select(RankedSnapshot)
            .join(
                sub,
                and_(
                    RankedSnapshot.tracked_player_id == sub.c.tracked_player_id,
                    RankedSnapshot.queue_type == sub.c.queue_type,
                    RankedSnapshot.fetched_at == sub.c.mx,
                ),
            )
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_latest_snapshot_before(
        self,
        session: AsyncSession,
        tracked_player_id: uuid.UUID,
        queue_type: str,
        fetched_at: datetime,
    ) -> RankedSnapshot | None:
        stmt = (
            select(RankedSnapshot)
            .where(
                RankedSnapshot.tracked_player_id == tracked_player_id,
                RankedSnapshot.queue_type == queue_type,
                RankedSnapshot.fetched_at <= fetched_at,
            )
            .order_by(RankedSnapshot.fetched_at.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_earliest_snapshot_after(
        self,
        session: AsyncSession,
        tracked_player_id: uuid.UUID,
        queue_type: str,
        fetched_at: datetime,
    ) -> RankedSnapshot | None:
        stmt = (
            select(RankedSnapshot)
            .where(
                RankedSnapshot.tracked_player_id == tracked_player_id,
                RankedSnapshot.queue_type == queue_type,
                RankedSnapshot.fetched_at >= fetched_at,
            )
            .order_by(RankedSnapshot.fetched_at.asc())
            .limit(1)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_latest_snapshot(
        self,
        session: AsyncSession,
        tracked_player_id: uuid.UUID,
        queue_type: str,
    ) -> RankedSnapshot | None:
        stmt = (
            select(RankedSnapshot)
            .where(
                RankedSnapshot.tracked_player_id == tracked_player_id,
                RankedSnapshot.queue_type == queue_type,
            )
            .order_by(RankedSnapshot.fetched_at.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def delete_player_snapshots(self, session: AsyncSession, player_id: uuid.UUID) -> None:
        await session.execute(
            RankedSnapshot.__table__.delete().where(RankedSnapshot.tracked_player_id == player_id)
        )
        await session.commit()
