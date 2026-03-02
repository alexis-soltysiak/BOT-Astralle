from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.features.matches.repository import MatchesRepository
from app.features.publications.repository import PublicationsRepository
from app.features.tracked_players.repository import TrackedPlayersRepository
from app.features.tracked_players.schemas import TrackedPlayerCreate, TrackedPlayerOut, TrackedPlayerPatch
from app.features.tracked_players.service import TrackedPlayersService

router = APIRouter(tags=["tracked_players"])


def get_service() -> TrackedPlayersService:
    return TrackedPlayersService(
        TrackedPlayersRepository(),
        MatchesRepository(),
        PublicationsRepository(),
    )


@router.get("/tracked-players", response_model=list[TrackedPlayerOut])
async def list_tracked_players(
    session: AsyncSession = Depends(get_session),
    service: TrackedPlayersService = Depends(get_service),
) -> list[TrackedPlayerOut]:
    items = await service.list(session)
    return items


@router.post(
    "/tracked-players",
    response_model=TrackedPlayerOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_tracked_player(
    payload: TrackedPlayerCreate,
    session: AsyncSession = Depends(get_session),
    service: TrackedPlayersService = Depends(get_service),
) -> TrackedPlayerOut:
    try:
        item = await service.create(session, payload)
        return item
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tracked-players/{player_id}", response_model=TrackedPlayerOut)
async def get_tracked_player(
    player_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    service: TrackedPlayersService = Depends(get_service),
) -> TrackedPlayerOut:
    item = await service.get(session, player_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not_found")
    return item


@router.patch("/tracked-players/{player_id}", response_model=TrackedPlayerOut)
async def patch_tracked_player(
    player_id: uuid.UUID,
    payload: TrackedPlayerPatch,
    session: AsyncSession = Depends(get_session),
    service: TrackedPlayersService = Depends(get_service),
) -> TrackedPlayerOut:
    item = await service.get(session, player_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not_found")
    return await service.patch(session, item, payload)


@router.delete("/tracked-players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tracked_player(
    player_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    service: TrackedPlayersService = Depends(get_service),
) -> None:
    item = await service.get(session, player_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not_found")
    await service.delete(session, player_id)
    return None
