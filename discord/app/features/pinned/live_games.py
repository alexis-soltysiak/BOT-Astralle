from __future__ import annotations

import asyncio
import random

import discord

from app.core.backend_client import BackendClient
from app.features.live_games.embeds import build_live_games_embeds


def _role_fn(client: discord.Client):
    resolver = getattr(client, "emoji", None)
    return (lambda role: resolver.role(role)) if resolver else (lambda role: "")


def _champ_fn(client: discord.Client):
    resolver = getattr(client, "emoji", None)
    return (lambda champion: resolver.champ_from_filename(champion)) if resolver else (lambda champion: "")


def _rank_fn(client: discord.Client):
    resolver = getattr(client, "emoji", None)
    return (lambda tier: resolver.rank(tier)) if resolver else (lambda tier: "")


def _live_fn(client: discord.Client):
    resolver = getattr(client, "emoji", None)
    if not resolver:
        return lambda: ""

    def _resolve() -> str:
        for name in ("status_live", "live_status", "live_ping", "live_on", "live"):
            markup = resolver.by_emoji_name(name)
            if markup:
                return markup
        return ""

    return _resolve


async def ensure_live_message(
    *,
    bot: discord.Client,
    backend: BackendClient,
    guild_id: int,
    binding: dict,
) -> dict:
    guild = bot.get_guild(guild_id)
    if guild is None:
        return binding

    channel_id = int(binding.get("channel_id") or "0")
    ch = guild.get_channel(channel_id)
    if ch is None or not isinstance(ch, discord.TextChannel):
        return binding

    await asyncio.sleep(0.12 + random.random() * 0.08)
    rows = await backend.list_live_games_active()
    embeds = build_live_games_embeds(
        rows,
        role_emoji_fn=_role_fn(bot),
        champ_emoji_fn=_champ_fn(bot),
        rank_emoji_fn=_rank_fn(bot),
        live_emoji_fn=_live_fn(bot),
        refresh_interval_seconds=getattr(bot, "settings", None).live_refresh_interval_seconds
        if getattr(bot, "settings", None)
        else 60,
    )

    message_id = binding.get("message_id")
    if message_id:
        try:
            msg = await ch.fetch_message(int(message_id))
            await msg.edit(embeds=embeds)
            return binding
        except discord.NotFound:
            pass
        except discord.Forbidden:
            await backend.patch_discord_binding(
                "LIVE_GAMES_MESSAGE",
                guild_id,
                {"last_error": "forbidden_edit_live_message"},
            )
            return binding

    msg = await ch.send(embeds=embeds)
    updated = await backend.patch_discord_binding(
        "LIVE_GAMES_MESSAGE",
        guild_id,
        {"message_id": str(msg.id), "last_error": None},
    )
    return updated


async def refresh_live_message(
    *,
    bot: discord.Client,
    backend: BackendClient,
    guild_id: int,
    binding: dict,
) -> None:
    if not binding.get("is_enabled", True):
        return

    guild = bot.get_guild(guild_id)
    if guild is None:
        return

    channel_id = int(binding.get("channel_id") or "0")
    ch = guild.get_channel(channel_id)
    if ch is None or not isinstance(ch, discord.TextChannel):
        return

    await asyncio.sleep(0.12 + random.random() * 0.08)
    rows = await backend.list_live_games_active()
    embeds = build_live_games_embeds(
        rows,
        role_emoji_fn=_role_fn(bot),
        champ_emoji_fn=_champ_fn(bot),
        rank_emoji_fn=_rank_fn(bot),
        live_emoji_fn=_live_fn(bot),
        refresh_interval_seconds=getattr(bot, "settings", None).live_refresh_interval_seconds
        if getattr(bot, "settings", None)
        else 60,
    )

    message_id = binding.get("message_id")
    if not message_id:
        await ensure_live_message(bot=bot, backend=backend, guild_id=guild_id, binding=binding)
        return

    try:
        msg = await ch.fetch_message(int(message_id))
        await msg.edit(embeds=embeds)
    except discord.NotFound:
        await ensure_live_message(bot=bot, backend=backend, guild_id=guild_id, binding=binding)
    except discord.Forbidden:
        await backend.patch_discord_binding(
            "LIVE_GAMES_MESSAGE",
            guild_id,
            {"last_error": "forbidden_edit_live_message"},
        )
