from __future__ import annotations

import discord
from discord import app_commands

from app.core.backend_client import BackendClient


def register(tree: app_commands.CommandTree, backend: BackendClient) -> None:
    @tree.command(name="health", description="Check backend health")
    async def health(interaction: discord.Interaction) -> None:
        data = await backend.health()
        await interaction.response.send_message(f"backend: {data}", ephemeral=True)