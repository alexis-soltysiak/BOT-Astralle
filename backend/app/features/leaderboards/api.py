from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.features.leaderboards.repository import LeaderboardsRepository
from app.features.leaderboards.schemas import LeaderboardEntryOut
from app.features.leaderboards.service import LeaderboardsService
from app.features.tracked_players.repository import TrackedPlayersRepository

router = APIRouter(tags=["leaderboards"])


def get_service() -> LeaderboardsService:
    return LeaderboardsService(LeaderboardsRepository(), TrackedPlayersRepository())


@router.get("/leaderboards", response_model=list[LeaderboardEntryOut])
async def get_leaderboards(
    sort: str = "solo",
    session: AsyncSession = Depends(get_session),
    service: LeaderboardsService = Depends(get_service),
) -> list[LeaderboardEntryOut]:
    if sort not in {"solo", "flex"}:
        raise HTTPException(status_code=400, detail="invalid_sort")
    return await service.get_leaderboard(session, sort)


@router.post("/leaderboards/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_leaderboards(
    session: AsyncSession = Depends(get_session),
    service: LeaderboardsService = Depends(get_service),
) -> dict[str, int]:
    try:
        return await service.refresh(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))