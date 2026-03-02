from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from .models import DiscordBindingKey
from .repository import list_bindings, patch_binding, upsert_binding
from .schemas import BindingPatchIn, BindingUpsertIn


async def svc_list(session: AsyncSession, *, guild_id: str):
    return await list_bindings(session, guild_id=guild_id)


async def svc_upsert(session: AsyncSession, *, binding_key: DiscordBindingKey, payload: BindingUpsertIn):
    return await upsert_binding(
        session,
        guild_id=payload.guild_id,
        binding_key=binding_key,
        channel_id=payload.channel_id,
        message_id=payload.message_id,
        leaderboard_mode=payload.leaderboard_mode,
        is_enabled=payload.is_enabled,
        last_error=payload.last_error,
    )


async def svc_patch(session: AsyncSession, *, guild_id: str, binding_key: DiscordBindingKey, payload: BindingPatchIn):
    return await patch_binding(
        session,
        guild_id=guild_id,
        binding_key=binding_key,
        channel_id=payload.channel_id,
        message_id=payload.message_id,
        leaderboard_mode=payload.leaderboard_mode,
        is_enabled=payload.is_enabled,
        last_error=payload.last_error,
    )