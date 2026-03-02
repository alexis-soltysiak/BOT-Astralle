from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DiscordBindingKey, DiscordMessageBinding


async def get_binding(
    session: AsyncSession, *, guild_id: str, binding_key: DiscordBindingKey
) -> DiscordMessageBinding | None:
    stmt = select(DiscordMessageBinding).where(
        DiscordMessageBinding.guild_id == guild_id,
        DiscordMessageBinding.binding_key == binding_key,
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def list_bindings(session: AsyncSession, *, guild_id: str) -> list[DiscordMessageBinding]:
    stmt = select(DiscordMessageBinding).where(DiscordMessageBinding.guild_id == guild_id).order_by(
        DiscordMessageBinding.binding_key.asc()
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def upsert_binding(
    session: AsyncSession,
    *,
    guild_id: str,
    binding_key: DiscordBindingKey,
    channel_id: str,
    message_id: str | None,
    leaderboard_mode,
    is_enabled: bool,
    last_error: str | None,
) -> DiscordMessageBinding:
    existing = await get_binding(session, guild_id=guild_id, binding_key=binding_key)
    if existing is None:
        binding = DiscordMessageBinding(
            guild_id=guild_id,
            binding_key=binding_key,
            channel_id=channel_id,
            message_id=message_id,
            leaderboard_mode=leaderboard_mode,
            is_enabled=is_enabled,
            last_error=last_error,
        )
        session.add(binding)
        await session.flush()
        return binding

    existing.channel_id = channel_id
    existing.message_id = message_id
    existing.leaderboard_mode = leaderboard_mode
    existing.is_enabled = is_enabled
    existing.last_error = last_error
    await session.flush()
    return existing


async def patch_binding(
    session: AsyncSession,
    *,
    guild_id: str,
    binding_key: DiscordBindingKey,
    channel_id: str | None = None,
    message_id: str | None = None,
    leaderboard_mode=None,
    is_enabled: bool | None = None,
    last_error: str | None = None,
) -> DiscordMessageBinding | None:
    existing = await get_binding(session, guild_id=guild_id, binding_key=binding_key)
    if existing is None:
        return None

    if channel_id is not None:
        existing.channel_id = channel_id
    if message_id is not None:
        existing.message_id = message_id
    if leaderboard_mode is not None:
        existing.leaderboard_mode = leaderboard_mode
    if is_enabled is not None:
        existing.is_enabled = is_enabled
    if last_error is not None:
        existing.last_error = last_error

    await session.flush()
    return existing