from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import discord

from app.core.emoji_resolver import EmojiResolver
from app.features.scoring.score_image import make_score_png
from app.features.scoring.view import MatchScoreBreakdownView, MatchTrackedPlayersView


SUMMONER_SPELL_STEMS = {
    1: "SummonerBoost",
    3: "SummonerExhaust",
    4: "SummonerFlash",
    6: "SummonerHaste",
    7: "SummonerHeal",
    11: "SummonerSmite",
    12: "SummonerTeleport",
    13: "SummonerMana",
    14: "SummonerDot",
    21: "SummonerBarrier",
    30: "SummonerPoroThrow",
    31: "SummonerPoroRecall",
    32: "SummonerSnowball",
    39: "SummonerSnowURFSnowball_Mark",
    2201: "SummonerCherryFlash",
    2202: "SummonerCherryHold",
}

RUNE_STYLE_STEMS = {
    8000: "7201_Precision",
    8100: "7200_Domination",
    8200: "7202_Sorcery",
    8300: "7203_Whimsy",
    8400: "7204_Resolve",
}

KEYSTONE_STEMS = {
    8005: "PressTheAttack",
    8008: "LethalTempoTemp",
    8010: "Conqueror",
    8021: "FleetFootwork",
    8112: "Electrocute",
    8128: "DarkHarvest",
    8214: "SummonAery",
    8229: "ArcaneComet",
    8230: "PhaseRush",
    8351: "GlacialAugment",
    8360: "UnsealedSpellbook",
    8369: "FirstStrike",
    8437: "GraspOfTheUndying",
    8439: "VeteranAftershock",
    8465: "Guardian",
    9923: "HailOfBlades",
}

CATEGORY_META = [
    ("global", "Global"),
    ("vs_opponent", "Vs Opponent"),
    ("objectives", "Objectives"),
    ("team", "Team"),
    ("role", "Role"),
]
COMPACT_CATEGORY_META = [
    ("global", "\U0001F310"),
    ("vs_opponent", "\U0001F19A"),
    ("objectives", "\U0001F3AF"),
    ("team", "\U0001F465"),
    ("role", "\U0001F3AD"),
]
UNSCORED_MODE_TOKENS = ("arena", "cherry")
BLANK = "\u200b"
QUEUE_LABELS = {
    420: "SoloQ",
    440: "Flex",
    450: "ARAM",
    1700: "Arena",
}
RANK_ICON = {
    1: "1\uFE0F\u20E3",
    2: "2\uFE0F\u20E3",
    3: "3\uFE0F\u20E3",
    4: "4\uFE0F\u20E3",
    5: "5\uFE0F\u20E3",
    6: "6\uFE0F\u20E3",
    7: "7\uFE0F\u20E3",
    8: "8\uFE0F\u20E3",
    9: "9\uFE0F\u20E3",
    10: "\U0001F51F",
}
EMOJI_CDN_TEMPLATE = "https://cdn.discordapp.com/emojis/{emoji_id}.png?quality=lossless"


def _slug(value: str) -> str:
    chars: list[str] = []
    prev_us = False
    for ch in str(value or ""):
        if ch.isalnum():
            chars.append(ch.lower())
            prev_us = False
            continue
        if not prev_us:
            chars.append("_")
            prev_us = True
    return "".join(chars).strip("_")


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


def _safe_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except Exception:
        return 0.0


def _fmt_duration(seconds: Any) -> str:
    total = _safe_int(seconds)
    if total is None or total <= 0:
        return "?"
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m {secs:02d}s"


def _fmt_match_datetime(timestamp_ms: Any) -> str | None:
    raw = _safe_int(timestamp_ms)
    if raw is None or raw <= 0:
        return None
    try:
        dt = datetime.fromtimestamp(raw / 1000).astimezone()
    except Exception:
        return None
    return dt.strftime("%d/%m/%Y %H:%M")


def _kda(p: dict) -> str:
    k = p.get("kills")
    d = p.get("deaths")
    a = p.get("assists")
    if k is None or d is None or a is None:
        return "?"
    return f"{k}/{d}/{a}"


def _payload_for(p: dict) -> dict:
    payload = p.get("payload")
    return payload if isinstance(payload, dict) else {}


def _name_for(p: dict, tracked_by_puuid: dict[str, dict]) -> str:
    puuid = str(p.get("puuid") or "")
    tp = tracked_by_puuid.get(puuid) or {}
    name = str(tp.get("discord_display_name") or "").strip()
    if name:
        return name
    if tp.get("game_name") and tp.get("tag_line"):
        return f"{tp.get('game_name')}#{tp.get('tag_line')}"
    gn = p.get("riot_id_game_name") or "?"
    tl = p.get("riot_id_tag_line") or "?"
    return f"{gn}#{tl}"


def _role_for(participant: dict, score_payload: dict) -> str:
    role = str(score_payload.get("role") or "").upper().strip()
    if role in {"TOP", "JUNGLE", "MID", "ADC", "SUPPORT"}:
        return role
    payload = _payload_for(participant)
    raw = str(payload.get("teamPosition") or payload.get("individualPosition") or "").upper().strip()
    if raw == "MIDDLE":
        return "MID"
    if raw in {"BOTTOM", "BOT"}:
        return "ADC"
    if raw == "UTILITY":
        return "SUPPORT"
    if raw in {"TOP", "JUNGLE", "MID", "ADC", "SUPPORT"}:
        return raw
    return "UNKNOWN"


def _emoji_from_name(resolver: EmojiResolver | None, prefix: str, stem: str) -> str:
    if resolver is None or not stem:
        return ""
    return resolver.by_emoji_name(f"{prefix}_{_slug(stem)}")


def _spell_emoji(resolver: EmojiResolver | None, spell_id: Any) -> str:
    if resolver is None:
        return ""
    spell_num = _safe_int(spell_id)
    if spell_num is None or spell_num <= 0:
        return ""
    stem = SUMMONER_SPELL_STEMS.get(spell_num)
    if stem:
        emoji = _emoji_from_name(resolver, "spell", stem)
        if emoji:
            return emoji
    return resolver.spell_id(spell_num)


def _rune_style_emoji(resolver: EmojiResolver | None, style_id: Any) -> str:
    if resolver is None:
        return ""
    style_num = _safe_int(style_id)
    if style_num is None or style_num <= 0:
        return ""
    stem = RUNE_STYLE_STEMS.get(style_num)
    if stem:
        emoji = _emoji_from_name(resolver, "rune", stem)
        if emoji:
            return emoji
    return resolver.rune_id(style_num)


def _keystone_emoji(resolver: EmojiResolver | None, perk_id: Any) -> str:
    if resolver is None:
        return ""
    perk_num = _safe_int(perk_id)
    if perk_num is None or perk_num <= 0:
        return ""
    stem = KEYSTONE_STEMS.get(perk_num)
    if stem:
        emoji = _emoji_from_name(resolver, "rune", stem)
        if emoji:
            return emoji
    return resolver.rune_id(perk_num)


def _loadout_lines(participant: dict, resolver: EmojiResolver | None) -> tuple[str | None, str | None]:
    payload = _payload_for(participant)
    if not payload:
        return None, None

    spell_ids = [payload.get("summoner1Id"), payload.get("summoner2Id")]
    spell_icons = [icon for icon in (_spell_emoji(resolver, spell_id) for spell_id in spell_ids) if icon]

    perks = payload.get("perks")
    styles = perks.get("styles") if isinstance(perks, dict) else []
    style0 = styles[0] if isinstance(styles, list) and len(styles) > 0 and isinstance(styles[0], dict) else {}
    style1 = styles[1] if isinstance(styles, list) and len(styles) > 1 and isinstance(styles[1], dict) else {}
    selections0 = style0.get("selections") if isinstance(style0, dict) else []
    primary_selection = selections0[0] if isinstance(selections0, list) and selections0 else {}
    rune_icons = [
        _keystone_emoji(resolver, primary_selection.get("perk") if isinstance(primary_selection, dict) else None),
        _rune_style_emoji(resolver, style0.get("style") if isinstance(style0, dict) else None),
        _rune_style_emoji(resolver, style1.get("style") if isinstance(style1, dict) else None),
    ]
    rune_icons = [icon for icon in rune_icons if icon]

    item_icons: list[str] = []
    if resolver is not None:
        item_icons = [resolver.item(payload.get(f"item{i}")) for i in range(7)]
        item_icons = [icon for icon in item_icons if icon]

    spells_runes = None
    items = None
    if spell_icons or rune_icons:
        parts: list[str] = []
        if spell_icons:
            parts.append("Spells: " + " ".join(spell_icons))
        if rune_icons:
            parts.append("Runes: " + " ".join(rune_icons))
        spells_runes = " | ".join(parts)
    if item_icons:
        items = "Build: " + " ".join(item_icons)
    return spells_runes, items


def _team_kills(participants: list[dict], team_id: int | None) -> float:
    if team_id is None:
        return 0.0
    total = 0.0
    for participant in participants:
        if participant.get("team_id") == team_id:
            total += _safe_float(participant.get("kills"))
    return total


def _kill_participation(participant: dict, participants: list[dict]) -> str:
    team_id = participant.get("team_id")
    team_kills = _team_kills(participants, team_id if isinstance(team_id, int) else None)
    if team_kills <= 0:
        return "0.0%"
    kp = 100.0 * (_safe_float(participant.get("kills")) + _safe_float(participant.get("assists"))) / team_kills
    return f"{kp:.1f}%"


def _cs_lines(participant: dict, duration: Any) -> str:
    payload = _payload_for(participant)
    cs = _safe_float(payload.get("totalMinionsKilled")) + _safe_float(payload.get("neutralMinionsKilled"))
    seconds = max(_safe_float(duration), 1.0)
    cs_per_min = cs / (seconds / 60.0)
    return f"{int(cs)} ({cs_per_min:.1f}/min)"


def _arena_placement(participant: dict) -> int | None:
    payload = _payload_for(participant)
    if not payload:
        return None
    for key in ("subteamPlacement", "placement", "teamPlacement"):
        placement = _safe_int(payload.get(key))
        if placement is not None and placement > 0:
            return placement
    return None


def _game_type_label(mode: str | None, queue_id: int | None, ranked_queue_type: str | None = None) -> str:
    if ranked_queue_type == "RANKED_SOLO_5x5":
        return "SoloQ"
    if ranked_queue_type == "RANKED_FLEX_SR":
        return "Flex"
    if queue_id in QUEUE_LABELS:
        return QUEUE_LABELS[queue_id]
    if mode:
        return mode.title()
    if queue_id is not None:
        return f"Queue {queue_id}"
    return "Unknown"


def _is_unscored_mode(mode: str | None, queue_id: int | None = None, ranked_queue_type: str | None = None) -> bool:
    if ranked_queue_type in {"RANKED_SOLO_5x5", "RANKED_FLEX_SR"}:
        return False
    if queue_id in {420, 440}:
        return False
    raw = str(mode or "").strip().lower()
    return any(token in raw for token in UNSCORED_MODE_TOKENS)


def _lp_line(score_payload: dict, participant: dict, resolver: EmojiResolver | None = None) -> str | None:
    _ = participant
    rank_delta = score_payload.get("rank_delta_lp")
    new_rank = score_payload.get("rank_after")
    rank_before = score_payload.get("rank_before")
    if rank_delta is None and new_rank is None and rank_before is None:
        return None

    delta = _safe_int(rank_delta)
    if delta is None:
        delta_label = None
        prefix = ""
    elif delta > 0:
        delta_label = f"+{delta} LP"
        prefix = "\U0001F7E2"
    elif delta < 0:
        delta_label = f"{delta} LP"
        prefix = "\U0001F534"
    else:
        delta_label = "0 LP"
        prefix = "\u26AA"

    rank_label = str(new_rank or rank_before or "").strip()
    tier = ""
    division = ""
    lp = ""
    if rank_label:
        left, sep, right = rank_label.partition(" - ")
        bits = left.strip().split()
        if bits:
            tier = bits[0].strip().upper()
        if len(bits) > 1:
            division = bits[1].strip().upper()
        if sep:
            lp = right.strip()

    rank_icon = resolver.rank(tier) if resolver is not None and tier else ""

    delta_part = f"{prefix} {delta_label}".strip() if delta_label else ""
    rank_parts = [part for part in [rank_icon, division, lp] if part]
    rank_part = " ".join(rank_parts)

    parts = [part for part in [delta_part, rank_part] if part]
    return " | ".join(parts) if parts else None


def _rank_icon(rank: Any) -> str:
    value = _safe_int(rank)
    if value is None:
        return "?"
    return RANK_ICON.get(value, str(value))


def _final_score_rank(participant: dict, score_by_puuid: dict[str, dict]) -> int | None:
    puuid = str(participant.get("puuid") or "")
    score_payload = score_by_puuid.get(puuid) or {}
    if not puuid or not isinstance(score_payload, dict) or not score_payload:
        return None

    player_score = _safe_float(score_payload.get("final_score"))
    all_scores = [
        _safe_float(score.get("final_score"))
        for score in score_by_puuid.values()
        if isinstance(score, dict) and str(score.get("puuid") or "")
    ]
    if not all_scores:
        return None
    return 1 + sum(1 for score in all_scores if score > player_score)


def _final_score_line(participant: dict, score_by_puuid: dict[str, dict]) -> str | None:
    puuid = str(participant.get("puuid") or "")
    score_payload = score_by_puuid.get(puuid) or {}
    if not puuid or not isinstance(score_payload, dict) or not score_payload:
        return None

    final_rank = _final_score_rank(participant, score_by_puuid)
    if final_rank is None:
        return None
    return f"\U0001F3C6 Classement final: **{_rank_icon(final_rank)}/10**"


def _compact_rank_summary_line(participant: dict, score_by_puuid: dict[str, dict]) -> str | None:
    puuid = str(participant.get("puuid") or "")
    score_payload = score_by_puuid.get(puuid) or {}
    if not puuid or not isinstance(score_payload, dict) or not score_payload:
        return None

    final_rank = _final_score_rank(participant, score_by_puuid)
    if final_rank is None:
        return None

    parts: list[str] = [f"\U0001F3C6{final_rank}/10"]
    cats = score_payload.get("categories")
    if isinstance(cats, dict):
        for key, icon in COMPACT_CATEGORY_META:
            cat = cats.get(key)
            if not isinstance(cat, dict):
                continue
            rank = _safe_int(cat.get("rank"))
            if rank is None:
                continue
            parts.append(f"{icon}{_rank_icon(rank)}")
    return " \u2022 ".join(parts)


def _categories_summary(score_payload: dict, resolver: EmojiResolver | None = None) -> str:
    cats = score_payload.get("categories")
    if not isinstance(cats, dict):
        return "Aucun score detaille"

    lines: list[str] = []
    for key, label in CATEGORY_META:
        cat = cats.get(key)
        if not isinstance(cat, dict):
            continue
        rank = cat.get("rank")
        if rank is None:
            continue
        icon = resolver.scoring_category(key) if resolver is not None else ""
        lines.append(f"{icon} {label}: {_rank_icon(rank)}/10")
    return "\n".join(lines) if lines else "Aucun score detaille"


def _categories_analysis_details(score_payload: dict) -> list[dict]:
    cats = score_payload.get("categories")
    if not isinstance(cats, dict):
        return []

    details: list[dict] = []
    for key, label in CATEGORY_META:
        cat = cats.get(key)
        if not isinstance(cat, dict):
            continue
        rank = _safe_int(cat.get("rank"))
        total_points = _safe_float(cat.get("total_points"))
        metrics_raw = cat.get("metrics")
        metrics: list[dict] = []
        if isinstance(metrics_raw, list):
            for metric in metrics_raw:
                if not isinstance(metric, dict):
                    continue
                metrics.append(
                    {
                        "label": str(metric.get("label") or "?"),
                        "value": round(_safe_float(metric.get("value")), 2),
                        "points": round(_safe_float(metric.get("points")), 2),
                    }
                )
        details.append(
            {
                "key": key,
                "label": label,
                "rank": rank,
                "total_points": round(total_points, 2),
                "metrics": metrics,
            }
        )
    return details


def _emoji_asset_url(emoji_markup: str) -> str | None:
    match = re.search(r"<a?:[^:]+:(\d+)>", emoji_markup or "")
    if not match:
        return None
    return EMOJI_CDN_TEMPLATE.format(emoji_id=match.group(1))


def _avatar_url(tracked: dict) -> str | None:
    url = tracked.get("discord_avatar_url")
    if isinstance(url, str) and url.strip():
        return url
    return None


def _focus_participant(
    participants: list[dict],
    tracked_by_puuid: dict[str, dict],
    focus_puuid: str | None = None,
) -> tuple[dict, dict] | None:
    if focus_puuid:
        target = str(focus_puuid).strip()
        for participant in participants:
            puuid = str(participant.get("puuid") or "")
            if puuid == target and puuid in tracked_by_puuid:
                return participant, tracked_by_puuid.get(puuid, {})

    tracked_parts = [
        participant for participant in participants if str(participant.get("puuid") or "") in tracked_by_puuid
    ]
    if not tracked_parts:
        return None
    participant = tracked_parts[0]
    tracked = tracked_by_puuid.get(str(participant.get("puuid") or ""), {})
    return participant, tracked


def _tracked_participants(participants: list[dict], tracked_by_puuid: dict[str, dict]) -> list[tuple[dict, dict]]:
    tracked_parts: list[tuple[dict, dict]] = []
    for participant in participants:
        puuid = str(participant.get("puuid") or "")
        if not puuid or puuid not in tracked_by_puuid:
            continue
        tracked_parts.append((participant, tracked_by_puuid.get(puuid, {})))
    tracked_parts.sort(key=lambda item: _name_for(item[0], tracked_by_puuid).lower())
    return tracked_parts


def _tracked_summary_lines(
    tracked_parts: list[tuple[dict, dict]],
    tracked_by_puuid: dict[str, dict],
) -> list[str]:
    lines: list[str] = []
    for participant, _tracked in tracked_parts:
        result = participant.get("win")
        if result is True:
            result_label = "W"
        elif result is False:
            result_label = "L"
        else:
            result_label = "?"
        lines.append(
            f"`{result_label}` {_name_for(participant, tracked_by_puuid)}"
            f" | {participant.get('champion_name') or '?'}"
            f" | {_kda(participant)}"
        )
    return lines


def _score_badge(
    participant: dict,
    score_by_puuid: dict[str, dict],
    participants: list[dict],
    resolver: EmojiResolver | None = None,
) -> str:
    puuid = str(participant.get("puuid") or "")
    score_payload = score_by_puuid.get(puuid) or {}
    if not puuid or not score_payload:
        return ""

    player_score = _safe_float(score_payload.get("final_score"))
    all_scores: dict[str, float] = {
        str(score.get("puuid") or ""): _safe_float(score.get("final_score"))
        for score in score_by_puuid.values()
        if str(score.get("puuid") or "")
    }
    if not all_scores:
        return ""

    win = participant.get("win")
    if win is True and player_score >= max(all_scores.values()):
        icon = resolver.by_emoji_name("mvp") if resolver is not None else ""
        return icon.strip()

    if win is False:
        team_id = _safe_int(participant.get("team_id"))
        team_puuids = {
            str(p.get("puuid") or "")
            for p in participants
            if _safe_int(p.get("team_id")) == team_id and str(p.get("puuid") or "")
        }
        team_scores = [score for p_id, score in all_scores.items() if p_id in team_puuids]
        if team_scores and player_score >= max(team_scores):
            icon = resolver.by_emoji_name("ace") if resolver is not None else ""
            return icon.strip()

    return ""


def should_request_match_analysis(summary: dict) -> bool:
    queue_id = _safe_int(summary.get("queue_id"))
    ranked_queue_type = str(summary.get("ranked_queue_type") or "").strip().upper()
    return ranked_queue_type in {"RANKED_SOLO_5x5", "RANKED_FLEX_SR"} or queue_id in {420, 440}


def build_match_analysis_context(
    summary: dict,
    tracked_by_puuid: dict[str, dict],
    focus_puuid: str | None = None,
) -> dict | None:
    if not should_request_match_analysis(summary):
        return None

    participants: list[dict] = summary.get("participants") or []
    scores: list[dict] = summary.get("scores") or []
    score_by_puuid = {str(score.get("puuid") or ""): score for score in scores if score.get("puuid")}
    focus = _focus_participant(participants, tracked_by_puuid, focus_puuid)
    if focus is None:
        return None

    participant, _tracked = focus
    puuid = str(participant.get("puuid") or "")
    score_payload = score_by_puuid.get(puuid) or {}
    if not isinstance(score_payload, dict) or not score_payload:
        return None

    queue_id = _safe_int(summary.get("queue_id"))
    ranked_queue_type = summary.get("ranked_queue_type")
    duration = summary.get("game_duration")
    final_rank = _final_score_rank(participant, score_by_puuid)
    final_score = _safe_float(score_payload.get("final_score"))
    lp_line = _lp_line(score_payload, participant, None)
    payload = _payload_for(participant)

    return {
        "player_name": _name_for(participant, tracked_by_puuid),
        "riot_match_id": str(summary.get("riot_match_id") or ""),
        "queue": _game_type_label(summary.get("game_mode"), queue_id, ranked_queue_type),
        "queue_id": queue_id,
        "ranked_queue_type": ranked_queue_type,
        "duration": _fmt_duration(duration),
        "result": "win" if participant.get("win") is True else "loss" if participant.get("win") is False else "unknown",
        "champion": str(participant.get("champion_name") or "?"),
        "role": _role_for(participant, score_payload),
        "kda": _kda(participant),
        "kp": _kill_participation(participant, participants),
        "cs": _cs_lines(participant, duration),
        "final_score": round(final_score, 2),
        "final_rank": final_rank,
        "rank_before": score_payload.get("rank_before"),
        "rank_after": score_payload.get("rank_after"),
        "rank_delta_lp": _safe_int(score_payload.get("rank_delta_lp")),
        "lp_line": lp_line,
        "notes_summary": _categories_summary(score_payload, None),
        "category_details": _categories_analysis_details(score_payload),
        "spells": [payload.get("summoner1Id"), payload.get("summoner2Id")],
        "items": [payload.get(f"item{i}") for i in range(7)],
    }


def build_match_finished_embed(
    summary: dict,
    tracked_by_puuid: dict[str, dict],
    resolver: EmojiResolver | None = None,
    analysis_payload_by_puuid: dict[str, dict] | None = None,
) -> tuple[discord.Embed, discord.File | None, discord.ui.View | None]:
    participants: list[dict] = summary.get("participants") or []
    scores: list[dict] = summary.get("scores") or []
    score_by_puuid = {str(score.get("puuid") or ""): score for score in scores if score.get("puuid")}
    tracked_parts = _tracked_participants(participants, tracked_by_puuid)
    focus = tracked_parts[0] if tracked_parts else None

    embed = discord.Embed(color=discord.Color.blurple())
    if focus is None:
        embed.title = f"Match finished - {summary.get('riot_match_id')}"
        embed.description = "Aucun joueur tracke dans ce match."
        return embed, None, None

    participant, tracked = focus
    tracked_summary_lines = _tracked_summary_lines(tracked_parts, tracked_by_puuid)
    queue_id = _safe_int(summary.get("queue_id"))
    ranked_queue_type = summary.get("ranked_queue_type")
    is_unscored_mode = _is_unscored_mode(summary.get("game_mode"), queue_id, ranked_queue_type)
    duration = summary.get("game_duration")
    match_datetime = _fmt_match_datetime(summary.get("game_end_ts")) or _fmt_match_datetime(
        summary.get("game_start_ts")
    )
    if len(tracked_parts) == 1:
        puuid = str(participant.get("puuid") or "")
        player_name = _name_for(participant, tracked_by_puuid)
        score_payload = score_by_puuid.get(puuid) or {}
        mode = _game_type_label(summary.get("game_mode"), queue_id, ranked_queue_type)
        role = _role_for(participant, score_payload if isinstance(score_payload, dict) else {})
        champ = str(participant.get("champion_name") or "?")
        role_icon = resolver.role(role) if resolver is not None else ""
        champ_icon = resolver.champ_from_filename(champ) if resolver is not None else ""
        champion_icon_url = _emoji_asset_url(champ_icon)
        avatar_url = _avatar_url(tracked)

        if champion_icon_url:
            embed.set_author(name=player_name, icon_url=champion_icon_url)
        elif avatar_url:
            embed.set_author(name=player_name, icon_url=avatar_url)
        else:
            embed.set_author(name=player_name)

        win = participant.get("win")
        if win is True:
            embed.color = discord.Color.green()
        elif win is False:
            embed.color = discord.Color.red()
        else:
            embed.color = discord.Color.blurple()

        spells_runes, items_line = _loadout_lines(participant, resolver)
        lp_line = None
        if not is_unscored_mode:
            lp_line = _lp_line(score_payload if isinstance(score_payload, dict) else {}, participant, resolver)
        badge_line = ""
        if not is_unscored_mode:
            badge_line = _score_badge(participant, score_by_puuid, participants, resolver)

        info_lines: list[str] = []
        if lp_line:
            info_lines.append(" ".join(part for part in [badge_line, lp_line] if part))
            info_lines.append(" ".join(part for part in ["\U0001F3AE", role_icon, mode] if part))
        else:
            info_lines.append(" ".join(part for part in [badge_line, "\U0001F3AE", role_icon, mode] if part))
        info_lines.append(f"\u23F1\uFE0F {_fmt_duration(duration)}")

        stats_lines: list[str] = [f"\u2694\uFE0F KDA: **{_kda(participant)}**"]
        arena_placement = _arena_placement(participant) if queue_id == 1700 else None
        if arena_placement is not None:
            stats_lines.append(f"\U0001F3C6 TOP **{arena_placement}**")
        else:
            stats_lines.append(f"\U0001F91D KP: **{_kill_participation(participant, participants)}**")
            stats_lines.append(f"\U0001F33E CS: **{_cs_lines(participant, duration)}**")
        embed.add_field(name=BLANK, value="\n".join(info_lines), inline=True)
        embed.add_field(name=BLANK, value="\n".join(stats_lines), inline=True)

        loadout_value_lines: list[str] = []
        if spells_runes:
            loadout_value_lines.append(spells_runes)
        if items_line:
            loadout_value_lines.append(items_line)
        if loadout_value_lines:
            embed.add_field(name=BLANK, value="\n".join(loadout_value_lines), inline=False)

        if not is_unscored_mode and isinstance(score_payload, dict) and score_payload:
            notes_lines: list[str] = []
            compact_line = _compact_rank_summary_line(participant, score_by_puuid)
            if compact_line:
                notes_lines.append(compact_line)
            else:
                final_score_line = _final_score_line(participant, score_by_puuid)
                if final_score_line:
                    notes_lines.append(final_score_line)
                notes_lines.append(_categories_summary(score_payload, resolver))
            embed.add_field(name="Notes :", value="\n".join(notes_lines), inline=False)

        file: discord.File | None = None
        if not is_unscored_mode and isinstance(score_payload, dict) and score_payload:
            final_score = _safe_float(score_payload.get("final_score"))
            file = make_score_png(final_score)
            if file is not None:
                embed.set_thumbnail(url="attachment://score.png")

        analysis_embed: discord.Embed | None = None
        analysis_payload = (analysis_payload_by_puuid or {}).get(puuid)
        if analysis_payload:
            from app.features.matches.analysis import build_match_advice_embed

            analysis_embed = build_match_advice_embed(
                analysis_payload=analysis_payload,
                player_name=player_name,
                author_name=player_name,
                author_icon_url=champion_icon_url or avatar_url,
                embed_color=embed.color,
            )

        if match_datetime:
            embed.set_footer(text=f"Game date: {match_datetime}")

        view: discord.ui.View | None = None
        if not is_unscored_mode and isinstance(score_payload, dict) and score_payload:
            view = MatchScoreBreakdownView(
                base_embed=embed,
                score_payload=score_payload,
                player_name=player_name,
                author_icon_url=champion_icon_url or avatar_url,
                author_name=player_name,
                embed_color=embed.color,
                resolver=resolver,
                analysis_embed=analysis_embed,
            )
        return embed, file, view

    def _player_embed(participant: dict, tracked: dict) -> tuple[discord.Embed, str, str | None]:
        puuid = str(participant.get("puuid") or "")
        player_name = _name_for(participant, tracked_by_puuid)
        score_payload = score_by_puuid.get(puuid) or {}
        role = _role_for(participant, score_payload if isinstance(score_payload, dict) else {})
        mode = _game_type_label(summary.get("game_mode"), queue_id, ranked_queue_type)
        champ = str(participant.get("champion_name") or "?")
        role_icon = resolver.role(role) if resolver is not None else ""
        champ_icon = resolver.champ_from_filename(champ) if resolver is not None else ""
        champion_icon_url = _emoji_asset_url(champ_icon)
        avatar_url = _avatar_url(tracked)

        player_embed = discord.Embed(color=discord.Color.blurple())
        if champion_icon_url:
            player_embed.set_author(name=player_name, icon_url=champion_icon_url)
        elif avatar_url:
            player_embed.set_author(name=player_name, icon_url=avatar_url)
        else:
            player_embed.set_author(name=player_name)

        win = participant.get("win")
        if win is True:
            player_embed.color = discord.Color.green()
        elif win is False:
            player_embed.color = discord.Color.red()

        lp_line = None
        if not is_unscored_mode:
            lp_line = _lp_line(score_payload if isinstance(score_payload, dict) else {}, participant, resolver)

        badge_line = ""
        if not is_unscored_mode:
            badge_line = _score_badge(participant, score_by_puuid, participants, resolver)

        info_lines: list[str] = []
        if lp_line:
            info_lines.append(" ".join(part for part in [badge_line, lp_line] if part))
            info_lines.append(" ".join(part for part in ["\U0001F3AE", role_icon, mode] if part))
        else:
            info_lines.append(" ".join(part for part in [badge_line, "\U0001F3AE", role_icon, mode] if part))
        info_lines.append(f"\u23F1\uFE0F {_fmt_duration(duration)}")

        stats_lines: list[str] = [f"\u2694\uFE0F KDA: **{_kda(participant)}**"]
        arena_placement = _arena_placement(participant) if queue_id == 1700 else None
        if arena_placement is not None:
            stats_lines.append(f"\U0001F3C6 TOP **{arena_placement}**")
        else:
            stats_lines.append(f"\U0001F91D KP: **{_kill_participation(participant, participants)}**")
            stats_lines.append(f"\U0001F33E CS: **{_cs_lines(participant, duration)}**")

        player_embed.add_field(name=BLANK, value="\n".join(info_lines), inline=True)
        player_embed.add_field(name=BLANK, value="\n".join(stats_lines), inline=True)

        if len(tracked_summary_lines) > 1:
            player_embed.add_field(name="Tracked players", value="\n".join(tracked_summary_lines[:6]), inline=False)

        spells_runes, items_line = _loadout_lines(participant, resolver)
        loadout_lines: list[str] = []
        if spells_runes:
            loadout_lines.append(spells_runes)
        if items_line:
            loadout_lines.append(items_line)
        if loadout_lines:
            player_embed.add_field(name=BLANK, value="\n".join(loadout_lines), inline=False)

        if not is_unscored_mode and isinstance(score_payload, dict) and score_payload:
            compact_line = _compact_rank_summary_line(participant, score_by_puuid)
            if compact_line:
                player_embed.add_field(name="Classement", value=compact_line, inline=False)
            else:
                final_score_line = _final_score_line(participant, score_by_puuid)
                if final_score_line:
                    player_embed.add_field(name="Classement", value=final_score_line, inline=False)

        if match_datetime:
            player_embed.set_footer(text=f"Game date: {match_datetime}")
        return player_embed, player_name, champion_icon_url or avatar_url

    player_cards: list[dict] = []
    for participant, tracked in tracked_parts:
        puuid = str(participant.get("puuid") or "")
        if not puuid:
            continue
        player_embed, player_name, author_icon_url = _player_embed(participant, tracked)
        analysis_embed: discord.Embed | None = None
        analysis_payload = (analysis_payload_by_puuid or {}).get(puuid)
        if analysis_payload:
            from app.features.matches.analysis import build_match_advice_embed

            analysis_embed = build_match_advice_embed(
                analysis_payload=analysis_payload,
                player_name=player_name,
                author_name=player_name,
                author_icon_url=author_icon_url,
                embed_color=player_embed.color,
            )

        player_cards.append(
            {
                "puuid": puuid,
                "player_name": player_name,
                "base_embed": player_embed,
                "analysis_embed": analysis_embed,
            }
        )

    if not player_cards:
        return embed, None, None

    file: discord.File | None = None
    if len(player_cards) == 1 and not is_unscored_mode:
        only = player_cards[0]
        score_payload = score_by_puuid.get(only["puuid"]) or {}
        if isinstance(score_payload, dict) and score_payload:
            final_score = _safe_float(score_payload.get("final_score"))
            file = make_score_png(final_score)
            if file is not None:
                only["base_embed"].set_thumbnail(url="attachment://score.png")

    view: discord.ui.View | None = None
    if player_cards:
        view = MatchTrackedPlayersView(player_cards=player_cards)

    return player_cards[0]["base_embed"], file, view
