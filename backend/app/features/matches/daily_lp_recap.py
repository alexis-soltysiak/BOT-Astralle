from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.matches.models import Match, MatchParticipant
from app.features.publications.repository import PublicationsRepository
from app.features.scoring.models import MatchScore
from app.features.tracked_players.models import TrackedPlayer

QUEUE_LABELS = {
    420: "Solo/Duo",
    440: "Flex",
}


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


def _tz_from_settings() -> ZoneInfo:
    settings = get_settings()
    tz_name = str(settings.scheduler_timezone or "Europe/Paris").strip() or "Europe/Paris"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


async def enqueue_daily_lp_recap_event(session: AsyncSession) -> None:
    settings = get_settings()
    if not settings.daily_lp_recap_enabled:
        return

    tz = _tz_from_settings()
    now_local = datetime.now(timezone.utc).astimezone(tz)
    day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    target_local = now_local.replace(
        hour=settings.daily_lp_recap_hour,
        minute=settings.daily_lp_recap_minute,
        second=0,
        microsecond=0,
    )
    if now_local < target_local:
        return
    period_end_local = target_local
    if period_end_local <= day_start_local:
        return

    start_ms = int(day_start_local.astimezone(timezone.utc).timestamp() * 1000)
    end_ms = int(period_end_local.astimezone(timezone.utc).timestamp() * 1000)

    ended_at = func.coalesce(Match.game_end_ts, Match.game_start_ts)
    stmt = (
        select(
            TrackedPlayer.puuid,
            TrackedPlayer.discord_display_name,
            TrackedPlayer.game_name,
            TrackedPlayer.tag_line,
            Match.queue_id,
            MatchScore.payload,
        )
        .select_from(Match)
        .join(MatchParticipant, MatchParticipant.match_id == Match.id)
        .join(
            MatchScore,
            and_(MatchScore.match_id == Match.id, MatchScore.puuid == MatchParticipant.puuid),
        )
        .join(TrackedPlayer, TrackedPlayer.puuid == MatchParticipant.puuid)
        .where(
            TrackedPlayer.active.is_(True),
            Match.queue_id.in_(tuple(QUEUE_LABELS.keys())),
            ended_at.is_not(None),
            ended_at >= start_ms,
            ended_at < end_ms,
        )
    )

    res = await session.execute(stmt)
    rows = list(res.all())

    buckets: dict[tuple[str, int], dict[str, Any]] = defaultdict(
        lambda: {
            "puuid": "",
            "player_name": "",
            "riot_id": "",
            "queue_id": 0,
            "queue_label": "",
            "lp_delta": 0,
            "games": 0,
        }
    )
    players_seen: set[str] = set()

    for puuid, discord_name, game_name, tag_line, queue_id, score_payload in rows:
        queue_num = _safe_int(queue_id)
        if queue_num not in QUEUE_LABELS:
            continue
        payload = score_payload if isinstance(score_payload, dict) else {}
        lp_delta = _safe_int(payload.get("rank_delta_lp"))
        if lp_delta is None:
            continue

        puuid_s = str(puuid or "").strip()
        if not puuid_s:
            continue
        players_seen.add(puuid_s)

        key = (puuid_s, queue_num)
        b = buckets[key]
        b["puuid"] = puuid_s
        b["player_name"] = str(discord_name or game_name or "?").strip() or "?"
        b["riot_id"] = f"{str(game_name or '?').strip() or '?'}#{str(tag_line or '?').strip() or '?'}"
        b["queue_id"] = queue_num
        b["queue_label"] = QUEUE_LABELS[queue_num]
        b["lp_delta"] = int(b["lp_delta"]) + lp_delta
        b["games"] = int(b["games"]) + 1

    entries = [value for value in buckets.values() if int(value.get("games") or 0) > 0 and int(value.get("lp_delta") or 0) != 0]
    if not entries:
        return

    positives = sorted(
        [entry for entry in entries if int(entry["lp_delta"]) > 0],
        key=lambda item: (int(item["lp_delta"]), int(item["games"])),
        reverse=True,
    )[:5]
    negatives = sorted(
        [entry for entry in entries if int(entry["lp_delta"]) < 0],
        key=lambda item: (int(item["lp_delta"]), -int(item["games"])),
    )[:5]

    payload = {
        "date": day_start_local.date().isoformat(),
        "period_start_local": day_start_local.isoformat(),
        "period_end_local": period_end_local.isoformat(),
        "timezone": str(tz),
        "top_positive": positives,
        "top_negative": negatives,
        "total_players": len(players_seen),
        "total_games": sum(int(item.get("games") or 0) for item in entries),
        "total_lp_delta": sum(int(item.get("lp_delta") or 0) for item in entries),
    }

    dedupe_key = f"daily_lp_recap:{payload['date']}"
    repo = PublicationsRepository()
    created = await repo.try_create_event(
        session=session,
        event_type="daily_lp_recap",
        dedupe_key=dedupe_key,
        payload=payload,
        max_attempts=settings.publication_max_attempts,
    )
    if created:
        await session.commit()
