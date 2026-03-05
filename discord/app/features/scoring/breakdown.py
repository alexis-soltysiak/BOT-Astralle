from __future__ import annotations

import discord

from app.core.emoji_resolver import EmojiResolver

CATEGORY_NAMES = {
    "global": "Global",
    "vs_opponent": "Vs Opponent",
    "objectives": "Objectives",
    "team": "Team",
    "role": "Role",
}
CATEGORY_ORDER = ("global", "vs_opponent", "objectives", "team", "role")


def _emoji(points: float) -> str:
    if points > 0.0001:
        return "🟢"
    if points < -0.0001:
        return "🔴"
    return "⚪"


def _cat_title(cat: str, role: str) -> str:
    if cat == "role" and role and role != "UNKNOWN":
        return role.title()
    return CATEGORY_NAMES.get(cat, cat.title())


def build_category_breakdown_embed(
    *,
    cat: str,
    score_payload: dict,
    player_name: str,
    author_name: str | None = None,
    author_icon_url: str | None = None,
    embed_color: discord.Color | None = None,
    resolver: EmojiResolver | None = None,
) -> discord.Embed:
    role = str(score_payload.get("role") or "UNKNOWN")
    cats = score_payload.get("categories") or {}
    category = cats.get(cat) if isinstance(cats, dict) else None

    icon = resolver.scoring_category(cat) if resolver is not None else ""
    title = _cat_title(cat, role)
    embed = discord.Embed(
        title=" ".join(part for part in [icon, title] if part),
        color=embed_color or discord.Color.blurple(),
    )
    if author_name:
        if author_icon_url:
            embed.set_author(name=author_name, icon_url=author_icon_url)
        else:
            embed.set_author(name=author_name)

    if not isinstance(category, dict):
        embed.description = "Aucune donnee."
        return embed

    rank = category.get("rank")
    total_points = float(category.get("total_points") or 0.0)
    embed.description = f"{rank}/10 | Score total: {total_points:.2f}"

    metrics = category.get("metrics") or []
    if not isinstance(metrics, list) or not metrics:
        embed.add_field(name="\u200b", value="Aucun detail.", inline=False)
        return embed

    lines: list[str] = []
    for metric in metrics[:25]:
        if not isinstance(metric, dict):
            continue
        label = str(metric.get("label") or "?")
        value = float(metric.get("value") or 0.0)
        points = float(metric.get("points") or 0.0)
        lines.append(f"{_emoji(points)} **{label}**: `{value:.1f}` | `{points:+.1f}` pts")

    embed.add_field(name="\u200b", value="\n".join(lines) if lines else "Aucun detail.", inline=False)
    return embed


def build_compact_breakdown_embed(
    *,
    score_payload: dict,
    player_name: str,
    author_name: str | None = None,
    author_icon_url: str | None = None,
    embed_color: discord.Color | None = None,
    resolver: EmojiResolver | None = None,
) -> discord.Embed:
    role = str(score_payload.get("role") or "UNKNOWN")
    final_score = float(score_payload.get("final_score") or 0.0)
    final_grade = str(score_payload.get("final_grade") or "?")
    cats = score_payload.get("categories") or {}

    embed = discord.Embed(
        title="Scoring",
        color=embed_color or discord.Color.blurple(),
        description=f"{player_name} | {final_score:.2f}/100 | {final_grade}",
    )
    if author_name:
        if author_icon_url:
            embed.set_author(name=author_name, icon_url=author_icon_url)
        else:
            embed.set_author(name=author_name)

    if not isinstance(cats, dict):
        embed.add_field(name="\u200b", value="Aucune donnee de scoring.", inline=False)
        return embed

    for key in CATEGORY_ORDER:
        category = cats.get(key)
        if not isinstance(category, dict):
            continue
        label = _cat_title(key, role)
        icon = resolver.scoring_category(key) if resolver is not None else ""
        rank = category.get("rank")
        total_points = float(category.get("total_points") or 0.0)
        header = f"{icon} {label}".strip()

        metrics = category.get("metrics") or []
        metric_lines: list[str] = []
        if isinstance(metrics, list):
            for metric in metrics:
                if not isinstance(metric, dict):
                    continue
                metric_label = str(metric.get("label") or "?")
                metric_value = float(metric.get("value") or 0.0)
                metric_points = float(metric.get("points") or 0.0)
                metric_lines.append(
                    f"{_emoji(metric_points)} **{metric_label}**: `{metric_value:.1f}` | `{metric_points:+.1f} pts`"
                )

        embed.add_field(
            name=f"{header} | `{rank}/10` | `{total_points:.2f} pts`",
            value="\n".join(metric_lines[:8]) if metric_lines else "Aucun detail.",
            inline=False,
        )

    if not embed.fields:
        embed.add_field(name="\u200b", value="Aucune categorie disponible.", inline=False)
    return embed
