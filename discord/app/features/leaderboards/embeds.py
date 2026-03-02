from __future__ import annotations

import re
from collections.abc import Callable

import discord
from app.core.timezones import format_france_datetime

RANK_ORDER = {
    "IRON": 1,
    "BRONZE": 2,
    "SILVER": 3,
    "GOLD": 4,
    "PLATINUM": 5,
    "EMERALD": 6,
    "DIAMOND": 7,
    "MASTER": 8,
    "GRANDMASTER": 9,
    "CHALLENGER": 10,
}

DIVISION_ORDER = {"IV": 1, "III": 2, "II": 3, "I": 4}
PODIUM = {1: "🥇", 2: "🥈", 3: "🥉"}
EMOJI_CDN_TEMPLATE = "https://cdn.discordapp.com/emojis/{emoji_id}.png?quality=lossless"


def _fmt_rank(state: dict) -> str:
    tier = state.get("tier")
    div = state.get("division")
    lp = state.get("league_points")
    if tier is None:
        return "Unranked"
    if div is None or lp is None:
        return f"{tier.title()}"
    return f"{tier.title()} {div} - {lp} LP"


def _emoji_asset_url(emoji_markup: str) -> str | None:
    match = re.search(r"<a?:[^:]+:(\d+)>", emoji_markup or "")
    if not match:
        return None
    return EMOJI_CDN_TEMPLATE.format(emoji_id=match.group(1))


def _state_sort_key(state: dict) -> tuple[int, int, int]:
    tier = str(state.get("tier") or "").upper()
    division = str(state.get("division") or "").upper()
    lp = state.get("league_points")
    return (
        RANK_ORDER.get(tier, 0),
        DIVISION_ORDER.get(division, 0),
        int(lp) if isinstance(lp, int) else -1,
    )


def _is_ranked_row(row: dict, sort: str) -> bool:
    state = row.get(sort) or {}
    tier = state.get("tier")
    return isinstance(tier, str) and bool(tier.strip())


def _display_name(row: dict) -> str:
    name = str(row.get("discord_display_name") or "").strip()
    if name:
        return name
    game_name = str(row.get("game_name") or "").strip()
    tag_line = str(row.get("tag_line") or "").strip()
    if game_name and tag_line:
        return f"{game_name}#{tag_line}"
    return game_name or "Unknown"


def _place_label(position: int) -> str:
    medal = PODIUM.get(position)
    return medal if medal else f"#{position}"


def _format_refresh(value: str | None) -> str | None:
    if not value:
        return None
    formatted = format_france_datetime(value, with_seconds=False)
    return formatted


def build_leaderboard_embed(
    sort: str,
    rows: list[dict],
    rank_fn: Callable[[str], str] | None = None,
    top: int = 20,
) -> discord.Embed:
    rank_fn = rank_fn or (lambda _: "")
    queue_label = "Solo/Duo Ranked Leaderboard Top20" if sort == "solo" else "Flex Ranked Leaderboard Top20"
    embed = discord.Embed(color=discord.Color.gold())
    embed.description = f"**{queue_label}**"

    challenger_icon_url = _emoji_asset_url(rank_fn("CHALLENGER"))
    if challenger_icon_url:
        embed.set_author(name="League of legends ranked", icon_url=challenger_icon_url)
    else:
        embed.set_author(name="League of legends ranked")

    ranked_rows = [row for row in rows if _is_ranked_row(row, sort)]
    top_rows = ranked_rows[:top]
    best_state = max((row.get(sort) or {} for row in top_rows), key=_state_sort_key, default={})
    best_icon_url = _emoji_asset_url(rank_fn(best_state.get("tier")))
    if best_icon_url:
        embed.set_thumbnail(url=best_icon_url)

    players_lines: list[str] = []
    ranks_lines: list[str] = []
    latest_refresh: str | None = None

    for index, row in enumerate(top_rows, start=1):
        state = row.get(sort) or {}
        players_lines.append(f"{_place_label(index)} {_display_name(row)}")
        tier = state.get("tier")
        icon = rank_fn(tier) if tier else ""
        icon_prefix = f"{icon} " if icon else ""
        ranks_lines.append(f"{icon_prefix}{_fmt_rank(state)}")

        fetched_at = state.get("fetched_at")
        if isinstance(fetched_at, str) and (latest_refresh is None or fetched_at > latest_refresh):
            latest_refresh = fetched_at

    if not players_lines:
        players_lines.append("Aucun joueur")
        ranks_lines.append("Aucune donnee")

    embed.add_field(name="Players", value="\n".join(players_lines), inline=True)
    embed.add_field(name="Rank Solo/Duo" if sort == "solo" else "Rank Flex", value="\n".join(ranks_lines), inline=True)

    formatted_refresh = _format_refresh(latest_refresh)
    if formatted_refresh:
        embed.set_footer(text=f"Dernier refresh: {formatted_refresh}")

    return embed
