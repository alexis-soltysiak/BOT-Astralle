from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.live_games.repository import LiveGamesRepository
from app.features.live_games.service import LiveGamesService
from app.features.tracked_players.repository import TrackedPlayersRepository


async def refresh_live_games_job(session: AsyncSession) -> None:
    service = LiveGamesService(LiveGamesRepository(), TrackedPlayersRepository())
    await service.refresh(session)