from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.features.leaderboards.repository import LeaderboardsRepository
from app.features.live_games.repository import LiveGamesRepository
from app.features.live_games.schemas import LiveGameOut
from app.features.live_games.service import LiveGamesService
from app.features.tracked_players.repository import TrackedPlayersRepository

router = APIRouter(tags=["live_games"])


def get_service() -> LiveGamesService:
    return LiveGamesService(
        LiveGamesRepository(),
        TrackedPlayersRepository(),
        LeaderboardsRepository(),
    )


@router.get("/live-games", response_model=list[LiveGameOut])
async def list_live_games(
    active_only: bool = False,
    session: AsyncSession = Depends(get_session),
    service: LiveGamesService = Depends(get_service),
) -> list[LiveGameOut]:
    return await service.list(session, only_active=active_only)


@router.get("/live-games/active", response_model=list[LiveGameOut])
async def list_active_live_games(
    session: AsyncSession = Depends(get_session),
    service: LiveGamesService = Depends(get_service),
) -> list[LiveGameOut]:
    return await service.list(session, only_active=True)


@router.post("/live-games/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_live_games(
    session: AsyncSession = Depends(get_session),
    service: LiveGamesService = Depends(get_service),
) -> dict[str, int]:
    try:
        return await service.refresh(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
