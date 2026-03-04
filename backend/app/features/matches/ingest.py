from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.leaderboards.repository import LeaderboardsRepository
from app.features.live_games.repository import LiveGamesRepository
from app.features.matches.repository import MatchesRepository
from app.features.matches.service import MatchesService
from app.features.publications.repository import PublicationsRepository
from app.features.tracked_players.repository import TrackedPlayersRepository


async def ingest_matches_job(session: AsyncSession) -> None:
    service = MatchesService(
        MatchesRepository(),
        TrackedPlayersRepository(),
        PublicationsRepository(),
        LeaderboardsRepository(),
        LiveGamesRepository(),
    )
    await service.ingest(session)
