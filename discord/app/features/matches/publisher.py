from __future__ import annotations

import asyncio
import structlog
import discord

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


def _avatar_url_for(bot: discord.Client, guild: discord.Guild | None, tracked: dict) -> str | None:
    discord_user_id = tracked.get("discord_user_id")
    if not discord_user_id:
        return None
    try:
        user_id = int(str(discord_user_id))
    except Exception:
        return None

    member = guild.get_member(user_id) if guild is not None else None
    if member is not None:
        return str(member.display_avatar.url)

    user = bot.get_user(user_id)
    if user is not None:
        return str(user.display_avatar.url)
    return None


async def run_outbox_publisher(
    bot: discord.Client,
    backend: BackendClient,
    consumer_id: str,
    poll_interval_seconds: int,
    guild_id: int | None,
) -> None:
    log = structlog.get_logger("publisher")

    while not bot.is_closed():
        try:
            events = await backend.claim_publication_events(consumer_id=consumer_id, limit=10)
            if not events:
                await asyncio.sleep(poll_interval_seconds)
                continue

            finished_channel_id: int | None = None
            if guild_id is not None:
                bindings = await backend.list_discord_bindings(guild_id=guild_id)
                for b in bindings:
                    if str(b.get("binding_key") or "") == "FINISHED_GAMES_CHANNEL" and b.get("is_enabled", True):
                        try:
                            finished_channel_id = int(b.get("channel_id") or "0")
                        except Exception:
                            finished_channel_id = None
                        break

            for ev in events:
                ev_id = str(ev.get("id") or "")
                ev_type = str(ev.get("event_type") or "")
                payload = ev.get("payload") or {}

                try:
                    if ev_type != "match_finished":
                        await backend.ack_publication_event(ev_id, ok=True)
                        continue

                    if finished_channel_id is None:
                        await backend.ack_publication_event(ev_id, ok=False, error="missing_finished_channel_binding")
                        continue

                    riot_match_id = str(payload.get("riot_match_id") or "")
                    if not riot_match_id:
                        await backend.ack_publication_event(ev_id, ok=False, error="missing_riot_match_id")
                        continue

                    ch = bot.get_channel(finished_channel_id)
                    if ch is None:
                        await backend.ack_publication_event(ev_id, ok=False, error="channel_not_found")
                        continue

                    guild = ch.guild if isinstance(ch, discord.TextChannel) else None
                    tracked = await backend.list_tracked_players()
                    tracked_by_puuid = {}
                    for tracked_player in tracked:
                        puuid = str(tracked_player.get("puuid") or "")
                        if not puuid:
                            continue
                        enriched = dict(tracked_player)
                        avatar_url = _avatar_url_for(bot, guild, tracked_player)
                        if avatar_url:
                            enriched["discord_avatar_url"] = avatar_url
                        tracked_by_puuid[puuid] = enriched

                    summary = await backend.get_match_summary(riot_match_id)
                    if _is_remake_summary(summary):
                        await backend.ack_publication_event(ev_id, ok=True)
                        continue
                    resolver = getattr(bot, "emoji", None)
                    embed, file, view = build_match_finished_embed(summary, tracked_by_puuid, resolver)

                    if file is None and view is None:
                        await ch.send(embed=embed)  # type: ignore[attr-defined]
                    elif file is None:
                        await ch.send(embed=embed, view=view)  # type: ignore[attr-defined]
                    elif view is None:
                        await ch.send(embed=embed, files=[file])  # type: ignore[attr-defined]
                    else:
                        await ch.send(embed=embed, files=[file], view=view)  # type: ignore[attr-defined]
                    await backend.ack_publication_event(ev_id, ok=True)

                except Exception as e:
                    log.error("publish_failed", event_id=ev_id, error=str(e))
                    await backend.ack_publication_event(ev_id, ok=False, error=str(e))

        except Exception as e:
            log.error("outbox_loop_error", error=str(e))

        await asyncio.sleep(poll_interval_seconds)
