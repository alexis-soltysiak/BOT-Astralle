from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.leaderboards.repository import LeaderboardsRepository
from app.features.leaderboards.service import LeaderboardsService
from app.features.tracked_players.repository import TrackedPlayersRepository


async def refresh_leaderboards_job(session: AsyncSession) -> None:
    service = LeaderboardsService(LeaderboardsRepository(), TrackedPlayersRepository())
    await service.refresh(session)