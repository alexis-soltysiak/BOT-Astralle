from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from .models import DiscordBindingKey
from .schemas import BindingOut, BindingPatchIn, BindingUpsertIn
from .service import svc_list, svc_patch, svc_upsert

router = APIRouter(tags=["discord-bindings"])


@router.get("/discord-bindings", response_model=list[BindingOut])
async def list_discord_bindings(
    guild_id: str = Query(..., min_length=1),
    session: AsyncSession = Depends(get_session),
):
    return await svc_list(session, guild_id=guild_id)


@router.put("/discord-bindings/{binding_key}", response_model=BindingOut)
async def upsert_discord_binding(
    binding_key: DiscordBindingKey,
    payload: BindingUpsertIn,
    session: AsyncSession = Depends(get_session),
):
    binding = await svc_upsert(session, binding_key=binding_key, payload=payload)
    await session.commit()
    await session.refresh(binding)
    return binding


@router.patch("/discord-bindings/{binding_key}", response_model=BindingOut)
async def patch_discord_binding(
    binding_key: DiscordBindingKey,
    guild_id: str = Query(..., min_length=1),
    payload: BindingPatchIn = ...,
    session: AsyncSession = Depends(get_session),
):
    binding = await svc_patch(session, guild_id=guild_id, binding_key=binding_key, payload=payload)
    if binding is None:
        raise HTTPException(status_code=404, detail="binding_not_found")
    await session.commit()
    await session.refresh(binding)
    return binding
