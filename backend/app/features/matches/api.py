from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import require_admin_frontend_access, require_admin_or_discord_service
from app.features.leaderboards.repository import LeaderboardsRepository
from app.features.matches.repository import MatchesRepository
from app.features.matches.service import MatchesService
from app.features.publications.repository import PublicationsRepository
from app.features.tracked_players.repository import TrackedPlayersRepository
from app.features.matches.schemas import MatchOut, MatchSummaryOut

router = APIRouter(tags=["matches"])


def get_service() -> MatchesService:
    return MatchesService(
        MatchesRepository(),
        TrackedPlayersRepository(),
        PublicationsRepository(),
        LeaderboardsRepository(),
    )


@router.get("/matches", response_model=list[MatchOut])
async def list_matches(
    limit: int = 50,
    _: str = Depends(require_admin_frontend_access),
    session: AsyncSession = Depends(get_session),
    service: MatchesService = Depends(get_service),
) -> list[MatchOut]:
    return await service.list(session, limit)


@router.get("/matches/{riot_match_id}", response_model=MatchOut)
async def get_match(
    riot_match_id: str,
    _: str = Depends(require_admin_frontend_access),
    session: AsyncSession = Depends(get_session),
    service: MatchesService = Depends(get_service),
) -> MatchOut:
    m = await service.get(session, riot_match_id)
    if m is None:
        raise HTTPException(status_code=404, detail="not_found")
    return m


@router.post("/matches/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_matches(
    _: str = Depends(require_admin_frontend_access),
    session: AsyncSession = Depends(get_session),
    service: MatchesService = Depends(get_service),
) -> dict:
    try:
        return await service.ingest(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/matches/{riot_match_id}/summary", response_model=MatchSummaryOut)
async def get_match_summary(
    riot_match_id: str,
    _: str = Depends(require_admin_or_discord_service),
    session: AsyncSession = Depends(get_session),
    service: MatchesService = Depends(get_service),
) -> MatchSummaryOut:
    s = await service.get_summary(session, riot_match_id)
    if s is None:
        raise HTTPException(status_code=404, detail="not_found")
    return s
