from __future__ import annotations

import discord
from discord import app_commands

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


def register(tree: app_commands.CommandTree, backend: BackendClient) -> None:
    @tree.command(name="live", description="Show active live games")
    async def live(interaction: discord.Interaction) -> None:
        rows = await backend.list_live_games_active()
        embeds = build_live_games_embeds(
            rows,
            role_emoji_fn=_role_fn(interaction.client),
            champ_emoji_fn=_champ_fn(interaction.client),
            rank_emoji_fn=_rank_fn(interaction.client),
            live_emoji_fn=_live_fn(interaction.client),
            refresh_interval_seconds=getattr(interaction.client, "settings", None).live_refresh_interval_seconds
            if getattr(interaction.client, "settings", None)
            else 60,
        )
        await interaction.response.send_message(embeds=embeds)
