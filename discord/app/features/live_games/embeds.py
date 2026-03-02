from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone

import discord
from app.core.timezones import format_france_datetime

EMOJI_CDN_TEMPLATE = "https://cdn.discordapp.com/emojis/{emoji_id}.{ext}?quality=lossless"
RED_DOT_ICON_URL = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/72x72/1f534.png"
COMMUNITY_DRAGON_CHAMPION_ICON_URL = (
    "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/{champion_id}.png"
)
QUEUE_LABELS = {
    420: "Ranked SoloQ",
    440: "Ranked Flex",
}
BLUE_TEAM_ID = 100
RED_TEAM_ID = 200
BLURPLE_BLUE = discord.Color.from_rgb(113, 127, 245)


def _participant_for_row(row: dict) -> dict:
    payload = row.get("payload")
    if not isinstance(payload, dict):
        return {}

    participants = payload.get("participants")
    if not isinstance(participants, list):
        return {}

    row_game_name = str(row.get("game_name") or "").strip().lower()
    row_tag_line = str(row.get("tag_line") or "").strip().lower()
    row_puuid = str(row.get("puuid") or "").strip()

    for part in participants:
        if not isinstance(part, dict):
            continue
        puuid = str(part.get("puuid") or "").strip()
        if row_puuid and puuid and puuid == row_puuid:
            return part
        game_name = str(part.get("riotIdGameName") or "").strip().lower()
        tag_line = str(part.get("riotIdTagline") or "").strip().lower()
        if row_game_name and row_tag_line and game_name == row_game_name and tag_line == row_tag_line:
            return part
        riot_id = str(part.get("riotId") or "").strip().lower()
        if row_game_name and row_tag_line and riot_id == f"{row_game_name}#{row_tag_line}":
            return part

    return {}


def _normalize_role(value: str) -> str:
    raw = str(value or "").upper().strip()
    if raw == "MIDDLE":
        return "MID"
    if raw in {"BOTTOM", "BOT"}:
        return "ADC"
    if raw == "UTILITY":
        return "SUPPORT"
    return raw


def _role_for_row(row: dict) -> str:
    direct = row.get("role") or row.get("team_position") or ""
    if direct:
        return _normalize_role(str(direct))

    participant = _participant_for_row(row)
    payload_role = participant.get("teamPosition") or participant.get("individualPosition") or ""
    return _normalize_role(str(payload_role))


def _champ_for_row(row: dict) -> str:
    direct = row.get("champion_name") or row.get("champion") or ""
    if direct:
        return str(direct)

    participant = _participant_for_row(row)
    payload_champ = participant.get("championKey") or participant.get("championName") or ""
    return str(payload_champ)


def _champ_markup_for_participant(participant: dict, champ_emoji_fn: Callable[[str], str]) -> str:
    candidates = (
        participant.get("championName"),
        participant.get("championKey"),
        participant.get("champion"),
    )
    for candidate in candidates:
        value = str(candidate or "").strip()
        if not value or value.isdigit():
            continue
        markup = champ_emoji_fn(value)
        if markup:
            return markup
    return ""


def _champion_icon_url_for_row(row: dict, champ_markup: str) -> str | None:
    emoji_url = _emoji_asset_url(champ_markup)
    if emoji_url:
        return emoji_url

    participant = _participant_for_row(row)
    champion_id = participant.get("championId")
    try:
        champion_id_int = int(champion_id)
    except Exception:
        return None
    if champion_id_int <= 0:
        return None
    return COMMUNITY_DRAGON_CHAMPION_ICON_URL.format(champion_id=champion_id_int)


def _emoji_asset_url(emoji_markup: str) -> str | None:
    match = re.search(r"<(a?):[^:]+:(\d+)>", emoji_markup or "")
    if not match:
        return None
    ext = "gif" if match.group(1) == "a" else "png"
    return EMOJI_CDN_TEMPLATE.format(emoji_id=match.group(2), ext=ext)


def _tracked_display_name(row: dict) -> str:
    name = str(row.get("discord_display_name") or "").strip()
    if name:
        return name
    riot_id = _riot_id_label(row)
    return riot_id if riot_id != "#" else "Unknown"


def _riot_id_label(row: dict) -> str:
    game_name = str(row.get("game_name") or "").strip()
    tag_line = str(row.get("tag_line") or "").strip()
    if game_name and tag_line:
        return f"{game_name}#{tag_line}"
    return game_name or tag_line or "#"


def _queue_id(payload: dict) -> int | None:
    value = payload.get("gameQueueConfigId") or payload.get("queueId")
    try:
        return int(value)
    except Exception:
        return None


def _queue_label(payload: dict) -> str:
    queue_id = _queue_id(payload)
    if queue_id is None:
        return "Custom / Unknown"
    return QUEUE_LABELS.get(queue_id, f"Queue {queue_id}")


def _tracked_state_for_row(row: dict, queue_id: int | None) -> dict:
    if queue_id == 440:
        return row.get("flex") or {}
    return row.get("solo") or {}


def _format_rank_short(state: dict, rank_emoji_fn: Callable[[str], str]) -> str:
    tier = str(state.get("tier") or "").strip().upper()
    division = str(state.get("division") or "").strip().upper()
    lp = state.get("league_points")
    if not tier:
        return "-"

    if tier in {"MASTER", "GRANDMASTER", "CHALLENGER"}:
        division = ""

    parts: list[str] = []
    icon = rank_emoji_fn(tier)
    if icon:
        parts.append(icon)
    if division:
        parts.append(division)
    if isinstance(lp, int):
        parts.append(f"{lp} LP")
    return " ".join(parts)


def _format_tracked_players(
    rows: list[dict],
    queue_id: int | None,
    rank_emoji_fn: Callable[[str], str],
) -> str:
    lines: list[str] = []
    for row in rows:
        state = _tracked_state_for_row(row, queue_id)
        lines.append(f"**{_tracked_display_name(row)}** {_format_rank_short(state, rank_emoji_fn)}")
    return "\n".join(lines) if lines else "Aucun joueur suivi"


def _participant_riot_name(participant: dict) -> str:
    riot_id = str(participant.get("riotId") or "").strip()
    if riot_id:
        return riot_id.split("#", 1)[0].strip() or riot_id
    game_name = str(participant.get("riotIdGameName") or "").strip()
    if game_name:
        return game_name
    summoner_name = str(participant.get("summonerName") or "").strip()
    if summoner_name:
        return summoner_name
    return "Unknown"


def _truncate_name(value: str, limit: int = 10) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[:limit]


def _participant_rank_text(
    participant: dict,
    tracked_rows_by_identity: dict[str, dict],
    queue_id: int | None,
    rank_emoji_fn: Callable[[str], str],
) -> str:
    ranked_state = participant.get("rankedState")
    if isinstance(ranked_state, dict):
        ranked_text = _format_rank_short(ranked_state, rank_emoji_fn)
        if ranked_text != "-":
            return ranked_text
    tracked = _tracked_row_for_participant(participant, tracked_rows_by_identity)
    if not tracked:
        return "-"
    return _format_rank_short(_tracked_state_for_row(tracked, queue_id), rank_emoji_fn)


def _participant_identity_keys(participant: dict) -> list[str]:
    keys: list[str] = []

    puuid = str(participant.get("puuid") or "").strip().lower()
    if puuid:
        keys.append(f"puuid:{puuid}")

    riot_id = str(participant.get("riotId") or "").strip().lower()
    if riot_id:
        keys.append(f"riot:{riot_id}")

    game_name = str(participant.get("riotIdGameName") or "").strip().lower()
    tag_line = str(participant.get("riotIdTagline") or "").strip().lower()
    if game_name and tag_line:
        keys.append(f"riot:{game_name}#{tag_line}")

    summoner_name = str(participant.get("summonerName") or "").strip().lower()
    if summoner_name:
        keys.append(f"summoner:{summoner_name}")

    return keys


def _tracked_identity_keys(row: dict) -> list[str]:
    keys: list[str] = []

    puuid = str(row.get("puuid") or "").strip().lower()
    if puuid:
        keys.append(f"puuid:{puuid}")

    game_name = str(row.get("game_name") or "").strip().lower()
    tag_line = str(row.get("tag_line") or "").strip().lower()
    if game_name and tag_line:
        keys.append(f"riot:{game_name}#{tag_line}")

    display_name = str(row.get("discord_display_name") or "").strip().lower()
    if display_name:
        keys.append(f"display:{display_name}")

    return keys


def _tracked_row_for_participant(participant: dict, tracked_rows_by_identity: dict[str, dict]) -> dict | None:
    for key in _participant_identity_keys(participant):
        tracked = tracked_rows_by_identity.get(key)
        if tracked is not None:
            return tracked
    return None


def _participant_is_tracked(participant: dict, tracked_rows_by_identity: dict[str, dict]) -> bool:
    return _tracked_row_for_participant(participant, tracked_rows_by_identity) is not None


def _team_value(
    participants: list[dict],
    team_id: int,
    tracked_rows_by_identity: dict[str, dict],
    champ_emoji_fn: Callable[[str], str],
    rank_emoji_fn: Callable[[str], str],
    queue_id: int | None,
) -> str:
    rows: list[str] = []
    for participant in participants:
        if int(participant.get("teamId") or 0) != team_id:
            continue
        champ = _champ_markup_for_participant(participant, champ_emoji_fn)
        name = _truncate_name(_participant_riot_name(participant))
        if _participant_is_tracked(participant, tracked_rows_by_identity):
            name = f"**{name}**"
        rank = _participant_rank_text(participant, tracked_rows_by_identity, queue_id, rank_emoji_fn)
        prefix = f"{champ} " if champ else ""
        suffix = f" {rank}" if rank and rank != "-" else ""
        rows.append(f"{prefix}{name}{suffix}")
    return "\n".join(rows[:5]) if rows else "-"


def _format_refresh(value: str | datetime | None) -> str:
    if value is None:
        return "unknown"
    formatted = format_france_datetime(value, with_seconds=True)
    return formatted or "unknown"


def _duration_label(payload: dict, fetched_at: str | datetime | None) -> str:
    start_ts = payload.get("gameStartTime") or payload.get("gameStartTimestamp")
    duration_seconds: int | None = None
    try:
        if start_ts:
            start_dt = datetime.fromtimestamp(int(start_ts) / 1000, tz=timezone.utc)
            if isinstance(fetched_at, datetime):
                now_dt = fetched_at if fetched_at.tzinfo else fetched_at.replace(tzinfo=timezone.utc)
            elif fetched_at:
                now_dt = datetime.fromisoformat(str(fetched_at).replace("Z", "+00:00"))
            else:
                now_dt = datetime.now(timezone.utc)
            duration_seconds = max(0, int((now_dt - start_dt).total_seconds()))
    except Exception:
        duration_seconds = None

    if duration_seconds is None:
        try:
            duration_seconds = int(payload.get("gameLength") or 0)
        except Exception:
            duration_seconds = 0

    minutes, seconds = divmod(duration_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    return f"{minutes:02d}m {seconds:02d}s"


def _author_name(primary_row: dict, tracked_rows: list[dict], live_markup: str) -> str:
    if live_markup:
        return f"LIVE GAME"
    return "LIVE GAME"


def build_live_games_embeds(
    rows: list[dict],
    role_emoji_fn: Callable[[str], str],
    champ_emoji_fn: Callable[[str], str],
    rank_emoji_fn: Callable[[str], str] | None = None,
    live_emoji_fn: Callable[[], str] | None = None,
    refresh_interval_seconds: int = 60,
) -> list[discord.Embed]:
    rank_emoji_fn = rank_emoji_fn or (lambda _: "")
    live_emoji_fn = live_emoji_fn or (lambda: "")

    empty = discord.Embed(title="Parties en cours", color=BLURPLE_BLUE)
    if not rows:
        empty.description = "Aucune partie en cours."
        empty.set_footer(text=f"Refresh: {_format_refresh(None)} | Frequence: {refresh_interval_seconds}s")
        return [empty]

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        game_id = str(row.get("game_id") or "").strip()
        if game_id:
            groups[game_id].append(row)

    embeds: list[discord.Embed] = []
    live_markup = live_emoji_fn()

    for _game_id, game_rows in list(groups.items())[:10]:
        tracked_rows = sorted(game_rows, key=lambda row: _tracked_display_name(row).lower())
        primary_row = tracked_rows[0]
        payload = primary_row.get("payload") if isinstance(primary_row.get("payload"), dict) else {}
        participants = payload.get("participants") if isinstance(payload.get("participants"), list) else []
        queue_id = _queue_id(payload)
        champ = _champ_for_row(primary_row)
        champ_markup = champ_emoji_fn(str(champ)) if champ else ""
        champ_icon_url = _champion_icon_url_for_row(primary_row, champ_markup)
        live_icon_url = RED_DOT_ICON_URL

        embed = discord.Embed(color=BLURPLE_BLUE)
        role = _role_for_row(primary_row)
        role_markup = role_emoji_fn(str(role)) if role else ""
        author_name = _author_name(primary_row, tracked_rows, live_markup)
        if role_markup:
            author_name = f"{role_markup} {author_name}"
        embed.set_author(name=author_name, icon_url=live_icon_url or None)

        embed.description = ""
        if champ_icon_url:
            embed.set_thumbnail(url=champ_icon_url)

        embed.add_field(
            name="\u200b",
            value=(
                f"{_format_tracked_players(tracked_rows, queue_id, rank_emoji_fn)}\n"
                f"Queue : **{_queue_label(payload)}**\n"
                f"⏱️  : **{_duration_label(payload, primary_row.get('fetched_at'))}**\n\u200b"
            ),
            inline=False,
        )

        tracked_rows_by_identity: dict[str, dict] = {}
        for row in tracked_rows:
            for key in _tracked_identity_keys(row):
                tracked_rows_by_identity[key] = row
        embed.add_field(
            name="Team 🔵",
            value=_team_value(
                participants,
                BLUE_TEAM_ID,
                tracked_rows_by_identity,
                champ_emoji_fn,
                rank_emoji_fn,
                queue_id,
            ),
            inline=True,
        )
        embed.add_field(
            name="Team 🔴",
            value=_team_value(
                participants,
                RED_TEAM_ID,
                tracked_rows_by_identity,
                champ_emoji_fn,
                rank_emoji_fn,
                queue_id,
            ),
            inline=True,
        )
        embed.set_footer(
            text=f"Refresh: {_format_refresh(primary_row.get('fetched_at'))} | Frequence: {refresh_interval_seconds}s"
        )
        embeds.append(embed)

    if embeds:
        return embeds

    empty.description = "Aucune partie en cours."
    empty.set_footer(text=f"Refresh: {_format_refresh(None)} | Frequence: {refresh_interval_seconds}s")
    return [empty]
