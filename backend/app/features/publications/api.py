from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.security import require_admin_frontend_access, require_discord_service_token
from app.features.publications.repository import PublicationsRepository
from app.features.publications.schemas import AckRequest, ClaimRequest, PublicationEventOut

router = APIRouter(tags=["publications"])


def get_repo() -> PublicationsRepository:
    return PublicationsRepository()


@router.get("/publication-events", response_model=list[PublicationEventOut])
async def list_publication_events(
    status_filter: str | None = None,
    limit: int = 50,
    _: str = Depends(require_admin_frontend_access),
    session: AsyncSession = Depends(get_session),
    repo: PublicationsRepository = Depends(get_repo),
) -> list[PublicationEventOut]:
    return await repo.list_events(session, status_filter, limit)


@router.post("/publication-events/claim", response_model=list[PublicationEventOut])
async def claim_publication_events(
    payload: ClaimRequest,
    _: None = Depends(require_discord_service_token),
    session: AsyncSession = Depends(get_session),
    repo: PublicationsRepository = Depends(get_repo),
) -> list[PublicationEventOut]:
    settings = get_settings()
    return await repo.claim(session, payload.consumer_id, payload.limit, settings.publication_lease_seconds)


@router.post("/publication-events/{event_id}/ack", response_model=PublicationEventOut)
async def ack_publication_event(
    event_id: uuid.UUID,
    payload: AckRequest,
    _: None = Depends(require_discord_service_token),
    session: AsyncSession = Depends(get_session),
    repo: PublicationsRepository = Depends(get_repo),
) -> PublicationEventOut:
    ev = await repo.ack(session, event_id, payload.ok, payload.error)
    if ev is None:
        raise HTTPException(status_code=404, detail="not_found")
    return ev
