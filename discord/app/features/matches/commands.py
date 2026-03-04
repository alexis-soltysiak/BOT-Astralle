from __future__ import annotations

import discord
import httpx
from discord import app_commands

from app.core.backend_client import BackendClient
from app.features.matches.analysis import build_recent_form_advice_embed
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


def _pick_tracked_player_for_user(tracked_players: list[dict], user_id: int) -> dict | None:
    user_id_str = str(user_id)
    candidates = [
        player
        for player in tracked_players
        if str(player.get("discord_user_id") or "") == user_id_str and bool(player.get("active", True))
    ]
    if not candidates:
        return None
    return candidates[0]


def _tracked_puuids_in_summary(summary: dict, tracked_by_puuid: dict[str, dict]) -> list[str]:
    puuids: list[str] = []
    for participant in summary.get("participants") or []:
        if not isinstance(participant, dict):
            continue
        puuid = str(participant.get("puuid") or "")
        if puuid and puuid in tracked_by_puuid and puuid not in puuids:
            puuids.append(puuid)
    return puuids


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
        analysis_payload_by_puuid: dict[str, dict] = {}
        if analyst is not None:
            for puuid in _tracked_puuids_in_summary(summary, tracked_by_puuid):
                payload = await analyst.generate(summary, tracked_by_puuid, focus_puuid=puuid)
                if payload:
                    analysis_payload_by_puuid[puuid] = payload
        embed, file, view = build_match_finished_embed(
            summary,
            tracked_by_puuid,
            resolver,
            analysis_payload_by_puuid=analysis_payload_by_puuid or None,
        )
        if file is None and view is None:
            await interaction.response.send_message(embed=embed)
        elif file is None:
            await interaction.response.send_message(embed=embed, view=view)
        elif view is None:
            await interaction.response.send_message(embed=embed, files=[file])
        else:
            await interaction.response.send_message(embed=embed, files=[file], view=view)

    @tree.command(name="last20", description="Analyse PRO sur les 20 derniers matchs d'un joueur tracke")
    @app_commands.describe(member="Membre Discord a analyser (par defaut: toi)")
    async def last20(interaction: discord.Interaction, member: discord.Member | None = None) -> None:
        await interaction.response.defer(thinking=True)
        target = member if member is not None else interaction.user

        try:
            tracked_players = await backend.list_tracked_players()
        except Exception as exc:
            await interaction.followup.send(f"Impossible de lire les joueurs trackes: {exc}", ephemeral=True)
            return

        tracked = _pick_tracked_player_for_user(tracked_players, target.id)
        if tracked is None:
            await interaction.followup.send(
                "Aucun compte LoL tracke pour ce membre. Utilise /link d'abord.",
                ephemeral=True,
            )
            return

        puuid = str(tracked.get("puuid") or "").strip()
        if not puuid:
            await interaction.followup.send("Compte tracke invalide: puuid manquant.", ephemeral=True)
            return

        try:
            recent = await backend.get_recent_player_analysis(puuid, limit=20)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                await interaction.followup.send("Aucune data match pour ce joueur.", ephemeral=True)
                return
            detail = exc.response.text[:400]
            await interaction.followup.send(
                f"Echec backend: {exc.response.status_code} {detail}",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(f"Echec analyse 20 matchs: {exc}", ephemeral=True)
            return

        aggregates = recent.get("aggregates") or {}
        if int(aggregates.get("matches_count") or 0) <= 0:
            await interaction.followup.send("Aucun match exploitable sur les 20 derniers.", ephemeral=True)
            return

        analyst = getattr(interaction.client, "match_analyst", None)
        analysis_payload = None if analyst is None else await analyst.generate_recent_form(recent)
        player_label = str(tracked.get("discord_display_name") or "").strip() or (
            f"{tracked.get('game_name') or '?'}#{tracked.get('tag_line') or '?'}"
        )
        avatar_url = _avatar_url_for(interaction, tracked)
        embed = build_recent_form_advice_embed(
            player_name=player_label,
            aggregates=aggregates,
            analysis_payload=analysis_payload,
            author_icon_url=avatar_url,
        )
        if analysis_payload and analysis_payload.get("headline"):
            embed.description = str(analysis_payload.get("headline"))
        await interaction.followup.send(embed=embed)
