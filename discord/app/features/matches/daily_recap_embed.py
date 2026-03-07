from __future__ import annotations

from datetime import datetime
from typing import Any

import discord


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _fmt_date(value: str | None) -> str:
    if not value:
        return "?"
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def _fmt_sign(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def _positive_emoji(lp_delta: int) -> str:
    if lp_delta >= 80:
        return "\U0001F680"
    if lp_delta >= 40:
        return "\U0001F525"
    if lp_delta >= 15:
        return "\U0001F4C8"
    return "\u2705"


def _negative_emoji(lp_delta: int) -> str:
    if lp_delta <= -80:
        return "\U0001F480"
    if lp_delta <= -40:
        return "\u26C8\uFE0F"
    if lp_delta <= -15:
        return "\U0001F4C9"
    return "\u26A0\uFE0F"


def _entry_line(entry: dict[str, Any], positive: bool) -> str | None:
    lp_delta = _safe_int(entry.get("lp_delta"))
    games = _safe_int(entry.get("games"))
    if lp_delta is None or games is None:
        return None
    player_name = str(entry.get("player_name") or "?").strip() or "?"
    riot_id = str(entry.get("riot_id") or "?").strip() or "?"
    queue_label = str(entry.get("queue_label") or "Ranked").strip() or "Ranked"
    game_label = "game" if games == 1 else "games"
    emoji = _positive_emoji(lp_delta) if positive else _negative_emoji(lp_delta)
    return (
        f"{emoji} **{_fmt_sign(lp_delta)} LP** : "
        f"**{player_name}** (`{riot_id}`) | {games} {game_label} / {queue_label}"
    )


def build_daily_lp_recap_embed(payload: dict[str, Any]) -> discord.Embed:
    top_positive = payload.get("top_positive")
    top_negative = payload.get("top_negative")
    positives = top_positive if isinstance(top_positive, list) else []
    negatives = top_negative if isinstance(top_negative, list) else []

    start_local = str(payload.get("period_start_local") or "")
    end_local = str(payload.get("period_end_local") or "")
    timezone_label = str(payload.get("timezone") or "local")
    total_games = _safe_int(payload.get("total_games")) or 0
    total_players = _safe_int(payload.get("total_players")) or 0
    total_lp_delta = _safe_int(payload.get("total_lp_delta")) or 0

    color = discord.Color.green() if total_lp_delta >= 0 else discord.Color.red()
    embed = discord.Embed(
        title="Recap LP du soir",
        description=f"Rank changes between **{_fmt_date(start_local)}** and **{_fmt_date(end_local)}**",
        color=color,
    )

    positive_lines = [line for line in (_entry_line(item, True) for item in positives) if line]
    negative_lines = [line for line in (_entry_line(item, False) for item in negatives) if line]

    embed.add_field(
        name="Most successful players",
        value="\n".join(positive_lines) if positive_lines else "Aucun gain LP notable aujourd'hui.",
        inline=False,
    )
    embed.add_field(
        name="Least successful players",
        value="\n".join(negative_lines) if negative_lines else "Aucune perte LP notable aujourd'hui.",
        inline=False,
    )
    embed.add_field(
        name="Daily snapshot",
        value=(
            f"\U0001F465 Players: **{total_players}**\n"
            f"\U0001F3AE Ranked games: **{total_games}**\n"
            f"\u2696\uFE0F Net LP: **{_fmt_sign(total_lp_delta)}**"
        ),
        inline=False,
    )
    embed.set_footer(text=f"Auto-post 23:00 ({timezone_label})")
    return embed
