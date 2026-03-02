from __future__ import annotations

import discord
from discord import app_commands

from app.core.backend_client import BackendClient
from app.features.leaderboards.embeds import build_leaderboard_embed


def register(tree: app_commands.CommandTree, backend: BackendClient) -> None:
    @tree.command(name="leaderboard", description="Show leaderboard (solo or flex)")
    @app_commands.choices(
        sort=[
            app_commands.Choice(name="solo", value="solo"),
            app_commands.Choice(name="flex", value="flex"),
        ]
    )
    async def leaderboard(
        interaction: discord.Interaction,
        sort: app_commands.Choice[str],
    ) -> None:
        rows = await backend.list_leaderboards(sort.value)
        resolver = getattr(interaction.client, "emoji", None)
        rank_fn = (lambda tier: resolver.rank(tier)) if resolver else (lambda tier: "")
        embed = build_leaderboard_embed(sort.value, rows, rank_fn)
        await interaction.response.send_message(embed=embed)
