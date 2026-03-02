from __future__ import annotations

import asyncio
import random

import discord
import httpx

from app.core.backend_client import BackendClient
from app.features.leaderboards.embeds import build_leaderboard_embed


def _rank_fn(client: discord.Client):
    resolver = getattr(client, "emoji", None)
    return (lambda tier: resolver.rank(tier)) if resolver else (lambda tier: "")


class LeaderboardPinnedView(discord.ui.View):
    def __init__(self, *, backend: BackendClient, guild_id: int, mode: str):
        super().__init__(timeout=None)
        self.backend = backend
        self.guild_id = guild_id
        self.mode = mode
        self.refresh_button.label = "Rafraichir"
        self.toggle_button.label = "Passer en Flex" if self.mode == "solo" else "Passer en SoloQ"

    @discord.ui.button(label="Rafraichir", style=discord.ButtonStyle.secondary, custom_id="leaderboard_refresh")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        _ = button
        await interaction.response.defer(thinking=False)
        await asyncio.sleep(0.12 + random.random() * 0.08)
        try:
            await self.backend.refresh_leaderboards()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            await interaction.followup.send(
                f"Echec du refresh leaderboard: {exc.response.status_code} {detail}",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"Echec du refresh leaderboard: {exc}",
                ephemeral=True,
            )
            return
        rows = await self.backend.list_leaderboards(self.mode)
        embed = build_leaderboard_embed(self.mode, rows, _rank_fn(interaction.client))
        await self.backend.patch_discord_binding(
            "LEADERBOARD_MESSAGE",
            self.guild_id,
            {"leaderboard_mode": self.mode, "last_error": None},
        )
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="...", style=discord.ButtonStyle.primary, custom_id="leaderboard_toggle")
    async def toggle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=False)
        new_mode = "flex" if self.mode == "solo" else "solo"
        await asyncio.sleep(0.12 + random.random() * 0.08)
        rows = await self.backend.list_leaderboards(new_mode)
        embed = build_leaderboard_embed(new_mode, rows, _rank_fn(interaction.client))
        await self.backend.patch_discord_binding(
            "LEADERBOARD_MESSAGE",
            self.guild_id,
            {"leaderboard_mode": new_mode, "last_error": None},
        )
        self.mode = new_mode
        button.label = "Passer en Flex" if self.mode == "solo" else "Passer en SoloQ"
        await interaction.message.edit(embed=embed, view=self)


async def ensure_leaderboard_message(
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

    mode = binding.get("leaderboard_mode") or "solo"

    await asyncio.sleep(0.12 + random.random() * 0.08)
    rows = await backend.list_leaderboards(mode)
    embed = build_leaderboard_embed(mode, rows, _rank_fn(bot))
    view = LeaderboardPinnedView(backend=backend, guild_id=guild_id, mode=mode)

    message_id = binding.get("message_id")
    if message_id:
        try:
            msg = await ch.fetch_message(int(message_id))
            await msg.edit(embed=embed, view=view)
            return binding
        except discord.NotFound:
            pass
        except discord.Forbidden:
            await backend.patch_discord_binding(
                "LEADERBOARD_MESSAGE",
                guild_id,
                {"last_error": "forbidden_edit_leaderboard_message"},
            )
            return binding

    msg = await ch.send(embed=embed, view=view)
    updated = await backend.patch_discord_binding(
        "LEADERBOARD_MESSAGE",
        guild_id,
        {"message_id": str(msg.id), "leaderboard_mode": mode, "last_error": None},
    )
    return updated


async def refresh_leaderboard_message(
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

    mode = binding.get("leaderboard_mode") or "solo"

    await asyncio.sleep(0.12 + random.random() * 0.08)
    rows = await backend.list_leaderboards(mode)
    embed = build_leaderboard_embed(mode, rows, _rank_fn(bot))
    view = LeaderboardPinnedView(backend=backend, guild_id=guild_id, mode=mode)

    message_id = binding.get("message_id")
    if not message_id:
        await ensure_leaderboard_message(bot=bot, backend=backend, guild_id=guild_id, binding=binding)
        return

    try:
        msg = await ch.fetch_message(int(message_id))
        await msg.edit(embed=embed, view=view)
    except discord.NotFound:
        await ensure_leaderboard_message(bot=bot, backend=backend, guild_id=guild_id, binding=binding)
    except discord.Forbidden:
        await backend.patch_discord_binding(
            "LEADERBOARD_MESSAGE",
            guild_id,
            {"last_error": "forbidden_edit_leaderboard_message"},
        )
