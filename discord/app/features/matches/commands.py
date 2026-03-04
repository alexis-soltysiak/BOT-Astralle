from __future__ import annotations

import discord
from discord import app_commands

from app.core.backend_client import BackendClient
from app.features.matches.embeds import build_match_finished_embed


def _is_remake_summary(summary: dict) -> bool:
    participants = summary.get("participants")
    if not isinstance(participants, list):
        return False

    for participant in participants:
        if not isinstance(participant, dict):
            continue
        payload = participant.get("payload")
        if isinstance(payload, dict) and payload.get("gameEndedInEarlySurrender") is True:
            return True
    return False


def _avatar_url_for(interaction: discord.Interaction, tracked: dict) -> str | None:
    discord_user_id = tracked.get("discord_user_id")
    if not discord_user_id:
        return None
    try:
        user_id = int(str(discord_user_id))
    except Exception:
        return None

    member = interaction.guild.get_member(user_id) if interaction.guild is not None else None
    if member is not None:
        return str(member.display_avatar.url)

    user = interaction.client.get_user(user_id)
    if user is not None:
        return str(user.display_avatar.url)
    return None


def register(tree: app_commands.CommandTree, backend: BackendClient) -> None:
    @tree.command(name="lastmatch", description="Send embed for last match in DB")
    async def lastmatch(interaction: discord.Interaction) -> None:
        matches = await backend.list_matches(limit=1)
        if not matches:
            await interaction.response.send_message("Aucun match en base.", ephemeral=True)
            return

        riot_match_id = matches[0].get("riot_match_id")
        if not riot_match_id:
            await interaction.response.send_message("Match invalide.", ephemeral=True)
            return

        tracked = await backend.list_tracked_players()
        tracked_by_puuid = {}
        for tracked_player in tracked:
            puuid = str(tracked_player.get("puuid") or "")
            if not puuid:
                continue
            enriched = dict(tracked_player)
            avatar_url = _avatar_url_for(interaction, tracked_player)
            if avatar_url:
                enriched["discord_avatar_url"] = avatar_url
            tracked_by_puuid[puuid] = enriched

        summary = await backend.get_match_summary(str(riot_match_id))
        if _is_remake_summary(summary):
            await interaction.response.send_message(
                "Le dernier match est un remake, aucun embed n'est publie.",
                ephemeral=True,
            )
            return
        resolver = getattr(interaction.client, "emoji", None)
        analyst = getattr(interaction.client, "match_analyst", None)
        analysis_payload = None if analyst is None else await analyst.generate(summary, tracked_by_puuid)
        embed, file, view = build_match_finished_embed(
            summary,
            tracked_by_puuid,
            resolver,
            analysis_payload=analysis_payload,
        )
        if file is None and view is None:
            await interaction.response.send_message(embed=embed)
        elif file is None:
            await interaction.response.send_message(embed=embed, view=view)
        elif view is None:
            await interaction.response.send_message(embed=embed, files=[file])
        else:
            await interaction.response.send_message(embed=embed, files=[file], view=view)
