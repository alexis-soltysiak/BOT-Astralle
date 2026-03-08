from __future__ import annotations

import asyncio
import math
import random
from datetime import datetime, timedelta, timezone

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.leaderboards.models import RankedSnapshot
from app.features.leaderboards.repository import LeaderboardsRepository
from app.features.leaderboards.schemas import RankedStateOut
from app.features.live_games.local_champion_map import load_local_champion_map
from app.features.live_games.repository import LiveGamesRepository
from app.features.live_games.schemas import LiveGameOut
from app.features.matches.models import Match
from app.features.scoring.engine import compute_match_scoring
from app.features.scoring.models import MatchScore
from app.features.tracked_players.repository import TrackedPlayersRepository
from app.infra.riot_client import RiotClient

QUEUE_SOLO = "RANKED_SOLO_5x5"
QUEUE_FLEX = "RANKED_FLEX_SR"
QUEUE_BY_ID = {
    420: QUEUE_SOLO,
    440: QUEUE_FLEX,
}
CHAMPION_SUMMARY_URL = (
    "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/en_us/v1/champion-summary.json"
)
_LOCAL_CHAMPION_MAP = load_local_champion_map()
_CHAMPION_CACHE: dict[int, dict[str, str]] = {}
_CHAMPION_CACHE_EXPIRES_AT: datetime | None = None
_PREDICTION_CACHE: dict[str, dict[str, object]] = {}
_PREDICTION_CACHE_TTL_SECONDS = 600
_RIOT_RECENT_SCORES_CACHE: dict[str, dict[str, object]] = {}
_RIOT_RECENT_SCORES_TTL_SECONDS = 900
_PREDICTION_MODEL_VERSION = "v1_weighted10_elo_lp"
_TEAM_IDS = (100, 200)
_BLUE_TEAM_ID = 100
_RED_TEAM_ID = 200
_RECENT_MATCH_LIMIT = 10
_RECENT_SCORE_WEIGHTS = [1.0, 1.0, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
_LAST3_RECENCY_MULTIPLIER = 1.35
_SCORE_COMPONENT_WEIGHT = 0.7
_ELO_COMPONENT_WEIGHT = 0.3
_PLAYER_BASELINE_SKILL = 0.5
_MAX_LP_NORMALIZER = 4400.0
_TIER_TO_INDEX = {
    "IRON": 0,
    "BRONZE": 1,
    "SILVER": 2,
    "GOLD": 3,
    "PLATINUM": 4,
    "EMERALD": 5,
    "DIAMOND": 6,
    "MASTER": 7,
    "GRANDMASTER": 8,
    "CHALLENGER": 9,
}
_DIVISION_TO_OFFSET = {"IV": 0, "III": 100, "II": 200, "I": 300}


def _state_from_snapshot(queue_type: str, snapshot: RankedSnapshot | None) -> RankedStateOut:
    return RankedStateOut(
        queue_type=queue_type,
        tier=None if snapshot is None else snapshot.tier,
        division=None if snapshot is None else snapshot.division,
        league_points=None if snapshot is None else snapshot.league_points,
        wins=None if snapshot is None else snapshot.wins,
        losses=None if snapshot is None else snapshot.losses,
        fetched_at=None if snapshot is None else snapshot.fetched_at,
    )


def _safe_int(value) -> int | None:  # type: ignore[no-untyped-def]
    try:
        return int(value)
    except Exception:
        return None


def _safe_float(value) -> float | None:  # type: ignore[no-untyped-def]
    try:
        return float(value)
    except Exception:
        return None


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _recent_weighted_score(scores: list[float]) -> float | None:
    if not scores:
        return None
    total_weight = 0.0
    weighted_sum = 0.0
    for index, score in enumerate(scores[:_RECENT_MATCH_LIMIT]):
        weight = _RECENT_SCORE_WEIGHTS[index] if index < len(_RECENT_SCORE_WEIGHTS) else _RECENT_SCORE_WEIGHTS[-1]
        if index < 3:
            weight *= _LAST3_RECENCY_MULTIPLIER
        weighted_sum += score * weight
        total_weight += weight
    if total_weight <= 0:
        return None
    return weighted_sum / total_weight


def _lp_total_from_ranked_state(ranked_state: dict | None) -> int | None:
    if not isinstance(ranked_state, dict):
        return None
    tier = str(ranked_state.get("tier") or "").strip().upper()
    if not tier:
        return None
    tier_index = _TIER_TO_INDEX.get(tier)
    if tier_index is None:
        return None
    lp_value = _safe_int(ranked_state.get("league_points"))
    if lp_value is None:
        return None
    division = str(ranked_state.get("division") or "").strip().upper()
    division_offset = _DIVISION_TO_OFFSET.get(division, 0)
    if tier in {"MASTER", "GRANDMASTER", "CHALLENGER"}:
        division_offset = 0
    return tier_index * 400 + division_offset + lp_value


def _normalized_elo_component(total_lp: int | None) -> float | None:
    if total_lp is None:
        return None
    return _clamp(total_lp / _MAX_LP_NORMALIZER, 0.0, 1.0)


def _player_skill_value(weighted_score: float | None, elo_component: float | None, games_count: int) -> float:
    score_component = None if weighted_score is None else _clamp(weighted_score / 100.0, 0.0, 1.0)
    raw = _PLAYER_BASELINE_SKILL
    if score_component is not None and elo_component is not None:
        raw = _SCORE_COMPONENT_WEIGHT * score_component + _ELO_COMPONENT_WEIGHT * elo_component
    elif score_component is not None:
        raw = score_component
    elif elo_component is not None:
        raw = elo_component
    score_confidence = _clamp(games_count / float(_RECENT_MATCH_LIMIT), 0.0, 1.0)
    if score_component is not None and elo_component is not None:
        # Keep ELO signal active even when we have only a few scored matches.
        confidence = max(score_confidence, 0.65)
    elif score_component is not None:
        confidence = score_confidence
    elif elo_component is not None:
        confidence = 0.65
    else:
        confidence = 0.0
    return _PLAYER_BASELINE_SKILL + (raw - _PLAYER_BASELINE_SKILL) * confidence


def _ranked_state_from_entry(queue_type: str, entry: dict | None) -> dict:
    if not isinstance(entry, dict):
        return {
            "queue_type": queue_type,
            "tier": None,
            "division": None,
            "league_points": None,
            "wins": None,
            "losses": None,
        }
    return {
        "queue_type": queue_type,
        "tier": entry.get("tier"),
        "division": entry.get("rank"),
        "league_points": entry.get("leaguePoints"),
        "wins": entry.get("wins"),
        "losses": entry.get("losses"),
    }


def _select_ranked_state(entries: list[dict], queue_id: int | None) -> dict:
    by_queue = {str(entry.get("queueType") or ""): entry for entry in entries if isinstance(entry, dict)}
    preferred_queue = QUEUE_BY_ID.get(queue_id)
    if preferred_queue:
        return _ranked_state_from_entry(preferred_queue, by_queue.get(preferred_queue))
    if QUEUE_SOLO in by_queue:
        return _ranked_state_from_entry(QUEUE_SOLO, by_queue.get(QUEUE_SOLO))
    if QUEUE_FLEX in by_queue:
        return _ranked_state_from_entry(QUEUE_FLEX, by_queue.get(QUEUE_FLEX))
    return _ranked_state_from_entry(preferred_queue or QUEUE_SOLO, None)


def _tracked_player_ranked_state(payload: dict, puuid: str, queue_type: str) -> dict | None:
    participants = payload.get("participants")
    if not isinstance(participants, list):
        return None

    state_key = "soloRankedState" if queue_type == QUEUE_SOLO else "flexRankedState"
    for participant in participants:
        if not isinstance(participant, dict):
            continue
        if str(participant.get("puuid") or "").strip() != puuid:
            continue
        state = participant.get(state_key)
        return state if isinstance(state, dict) else None
    return None


async def _get_champion_name_map() -> dict[int, dict[str, str]]:
    global _CHAMPION_CACHE, _CHAMPION_CACHE_EXPIRES_AT

    now = datetime.now(timezone.utc)
    if _CHAMPION_CACHE and _CHAMPION_CACHE_EXPIRES_AT is not None and now < _CHAMPION_CACHE_EXPIRES_AT:
        return _CHAMPION_CACHE

    mapping: dict[int, dict[str, str]] = dict(_LOCAL_CHAMPION_MAP)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(CHAMPION_SUMMARY_URL)
            res.raise_for_status()
            data = res.json()
    except Exception:
        _CHAMPION_CACHE = mapping
        _CHAMPION_CACHE_EXPIRES_AT = now + timedelta(hours=6)
        return _CHAMPION_CACHE

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            champion_id = _safe_int(item.get("id"))
            alias = str(item.get("alias") or "").strip()
            name = str(item.get("name") or "").strip()
            if champion_id is None or not alias:
                continue
            mapping[champion_id] = {
                "key": alias,
                "name": name or alias,
            }

    _CHAMPION_CACHE = mapping
    _CHAMPION_CACHE_EXPIRES_AT = now + timedelta(hours=6)
    return _CHAMPION_CACHE


class LiveGamesService:
    def __init__(
        self,
        repo: LiveGamesRepository,
        players_repo: TrackedPlayersRepository,
        leaderboards_repo: LeaderboardsRepository | None = None,
    ) -> None:
        self._repo = repo
        self._players_repo = players_repo
        self._leaderboards_repo = leaderboards_repo or LeaderboardsRepository()
        self._log = structlog.get_logger("live_games")

    async def _recent_scores_for_puuid(self, session: AsyncSession, puuid: str, limit: int = _RECENT_MATCH_LIMIT) -> list[float]:
        stmt = (
            select(MatchScore.final_score)
            .join(Match, Match.id == MatchScore.match_id)
            .where(MatchScore.puuid == puuid)
            .order_by(Match.created_at.desc())
            .limit(limit)
        )
        res = await session.execute(stmt)
        values: list[float] = []
        for row in res.all():
            score = _safe_float(row[0])
            if score is None:
                continue
            values.append(score)
        return values

    async def _riot_recent_scores_for_puuid(
        self,
        *,
        client: RiotClient,
        region: str,
        puuid: str,
        limit: int = _RECENT_MATCH_LIMIT,
    ) -> list[float]:
        cache_key = f"{region}:{puuid}"
        now = datetime.now(timezone.utc)
        cached = _RIOT_RECENT_SCORES_CACHE.get(cache_key)
        if isinstance(cached, dict):
            expires_at = cached.get("expires_at")
            if isinstance(expires_at, datetime) and now < expires_at:
                scores = cached.get("scores")
                if isinstance(scores, list):
                    return [float(value) for value in scores]

        await asyncio.sleep(0.02 + random.random() * 0.04)
        try:
            match_ids = await client.get_match_ids_by_puuid(region, puuid, 0, limit)
        except Exception:
            self._log.exception("live_prediction_riot_match_ids_failed", region=region, puuid=puuid)
            return []
        if not match_ids:
            _RIOT_RECENT_SCORES_CACHE[cache_key] = {
                "expires_at": now + timedelta(seconds=_RIOT_RECENT_SCORES_TTL_SECONDS),
                "scores": [],
            }
            return []

        sem = asyncio.Semaphore(3)

        async def _score_one_match(match_id: str) -> float | None:
            async with sem:
                await asyncio.sleep(0.03 + random.random() * 0.05)
                try:
                    match_payload = await client.get_match(region, match_id)
                    scores = await compute_match_scoring(match_payload)
                except Exception:
                    self._log.exception(
                        "live_prediction_riot_match_score_failed",
                        region=region,
                        puuid=puuid,
                        match_id=match_id,
                    )
                    return None
            target = next((row for row in scores if str(row.get("puuid") or "") == puuid), None)
            if not isinstance(target, dict):
                return None
            score = _safe_float(target.get("final_score"))
            return score

        raw_scores = await asyncio.gather(*(_score_one_match(match_id) for match_id in match_ids[:limit]))
        cleaned_scores = [float(score) for score in raw_scores if score is not None]
        _RIOT_RECENT_SCORES_CACHE[cache_key] = {
            "expires_at": now + timedelta(seconds=_RIOT_RECENT_SCORES_TTL_SECONDS),
            "scores": cleaned_scores,
        }
        return cleaned_scores

    def _participant_display_name(self, participant: dict) -> str:
        riot_id = str(participant.get("riotId") or "").strip()
        if riot_id:
            return riot_id
        game_name = str(participant.get("riotIdGameName") or "").strip()
        tag_line = str(participant.get("riotIdTagline") or "").strip()
        if game_name and tag_line:
            return f"{game_name}#{tag_line}"
        if game_name:
            return game_name
        summoner_name = str(participant.get("summonerName") or "").strip()
        if summoner_name:
            return summoner_name
        return "Unknown"

    def _prediction_cache_key(self, game_id: str, participants: list[dict]) -> str:
        pairs: list[str] = []
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            puuid = str(participant.get("puuid") or "").strip()
            team_id = _safe_int(participant.get("teamId"))
            if puuid and team_id in _TEAM_IDS:
                pairs.append(f"{team_id}:{puuid}")
        pairs.sort()
        return f"{game_id}|{'|'.join(pairs)}"

    async def _compute_prediction_for_game(
        self,
        *,
        session: AsyncSession,
        game_id: str,
        payload: dict,
        tracked_puuids: set[str] | None = None,
        riot_client: RiotClient | None = None,
        riot_region: str | None = None,
    ) -> dict | None:
        participants = payload.get("participants")
        if not isinstance(participants, list) or not participants:
            return None

        cache_key = self._prediction_cache_key(game_id, participants)
        now = datetime.now(timezone.utc)
        cached = _PREDICTION_CACHE.get(cache_key)
        if isinstance(cached, dict):
            expires_at = cached.get("expires_at")
            if isinstance(expires_at, datetime) and now < expires_at:
                prediction = cached.get("prediction")
                if isinstance(prediction, dict):
                    return prediction

        sem = asyncio.Semaphore(4)

        async def _one(participant: dict) -> dict | None:
            if not isinstance(participant, dict):
                return None
            puuid = str(participant.get("puuid") or "").strip()
            team_id = _safe_int(participant.get("teamId"))
            if not puuid or team_id not in _TEAM_IDS:
                return None
            is_tracked = puuid in (tracked_puuids or set())
            async with sem:
                await asyncio.sleep(0.02 + random.random() * 0.03)
                recent_scores = await self._recent_scores_for_puuid(session, puuid)
                if not recent_scores and riot_client is not None and riot_region:
                    recent_scores = await self._riot_recent_scores_for_puuid(
                        client=riot_client,
                        region=riot_region,
                        puuid=puuid,
                        limit=_RECENT_MATCH_LIMIT,
                    )
            weighted_score = _recent_weighted_score(recent_scores)
            lp_total = _lp_total_from_ranked_state(participant.get("rankedState"))
            elo_component = _normalized_elo_component(lp_total)
            skill = _player_skill_value(weighted_score, elo_component, len(recent_scores))
            games_count = len(recent_scores)
            if not is_tracked and games_count == 0:
                games_count = None
            return {
                "puuid": puuid,
                "player_name": self._participant_display_name(participant),
                "team_id": team_id,
                "is_tracked": is_tracked,
                "games_count": games_count,
                "recent_scores": [round(value, 2) for value in recent_scores],
                "weighted_recent_score": None if weighted_score is None else round(weighted_score, 2),
                "elo_lp_total": lp_total,
                "elo_component": None if elo_component is None else round(elo_component, 4),
                "skill_value": round(skill, 4),
            }

        raw_players = await asyncio.gather(*(_one(participant) for participant in participants))
        player_rows = [row for row in raw_players if isinstance(row, dict)]
        if not player_rows:
            return None

        team_values: dict[int, list[float]] = {_BLUE_TEAM_ID: [], _RED_TEAM_ID: []}
        for row in player_rows:
            team_id = _safe_int(row.get("team_id"))
            if team_id in _TEAM_IDS:
                team_values[team_id].append(float(row.get("skill_value") or _PLAYER_BASELINE_SKILL))

        if not team_values[_BLUE_TEAM_ID] and not team_values[_RED_TEAM_ID]:
            return None

        blue_strength = (
            sum(team_values[_BLUE_TEAM_ID]) / max(1, len(team_values[_BLUE_TEAM_ID]))
            if team_values[_BLUE_TEAM_ID]
            else _PLAYER_BASELINE_SKILL
        )
        red_strength = (
            sum(team_values[_RED_TEAM_ID]) / max(1, len(team_values[_RED_TEAM_ID]))
            if team_values[_RED_TEAM_ID]
            else _PLAYER_BASELINE_SKILL
        )
        # Smaller slope keeps V1 conservative when team data is incomplete.
        blue_prob = _clamp(_sigmoid((blue_strength - red_strength) * 6.0), 0.05, 0.95)
        red_prob = 1.0 - blue_prob

        prediction = {
            "model_version": _PREDICTION_MODEL_VERSION,
            "computed_at": now.isoformat(),
            "cache_ttl_seconds": _PREDICTION_CACHE_TTL_SECONDS,
            "formula": "team_skill=avg(player_skill), player_skill=blend(weighted_recent_score, elo_lp), prob=sigmoid(diff)",
            "weights": {
                "recent_scores": _RECENT_SCORE_WEIGHTS,
                "last3_multiplier": _LAST3_RECENCY_MULTIPLIER,
                "score_component_weight": _SCORE_COMPONENT_WEIGHT,
                "elo_component_weight": _ELO_COMPONENT_WEIGHT,
            },
            "team_blue": {
                "team_id": _BLUE_TEAM_ID,
                "strength": round(blue_strength, 4),
                "win_probability": round(blue_prob, 4),
                "players_count": len(team_values[_BLUE_TEAM_ID]),
            },
            "team_red": {
                "team_id": _RED_TEAM_ID,
                "strength": round(red_strength, 4),
                "win_probability": round(red_prob, 4),
                "players_count": len(team_values[_RED_TEAM_ID]),
            },
            "players": player_rows,
        }
        _PREDICTION_CACHE[cache_key] = {
            "expires_at": now + timedelta(seconds=_PREDICTION_CACHE_TTL_SECONDS),
            "prediction": prediction,
        }
        return prediction

    async def _fetch_active_game_with_fallback(
        self,
        *,
        client: RiotClient,
        platform: str,
        puuid: str,
        player_id: str,
    ) -> dict | None:
        try:
            summoner = await client.get_summoner_by_puuid(platform, puuid)
        except Exception:
            self._log.exception(
                "live_game_summoner_lookup_failed",
                player_id=player_id,
                platform=platform,
            )
            raise

        summoner_id = str(summoner.get("id") or "").strip()
        if summoner_id:
            try:
                return await client.get_active_game(platform, summoner_id)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                raise

        self._log.warning(
            "live_game_missing_summoner_id_using_puuid_fallback",
            player_id=player_id,
            platform=platform,
        )
        try:
            game = await client.get_active_game(platform, puuid)
            self._log.warning(
                "live_game_puuid_fallback_succeeded",
                player_id=player_id,
                platform=platform,
            )
            return game
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self._log.info(
                    "live_game_puuid_fallback_not_found",
                    player_id=player_id,
                    platform=platform,
                )
                return None
            raise

    async def _enrich_live_game_payload(
        self,
        *,
        game: dict,
        platform: str,
        client: RiotClient,
    ) -> dict:
        payload = dict(game)
        participants = payload.get("participants")
        if not isinstance(participants, list):
            return payload

        queue_id = _safe_int(payload.get("gameQueueConfigId") or payload.get("queueId"))
        try:
            champion_name_map = await _get_champion_name_map()
        except Exception:
            champion_name_map = dict(_CHAMPION_CACHE)
            if champion_name_map:
                self._log.warning(
                    "live_game_champion_map_fetch_failed_using_stale_cache",
                    champions=len(champion_name_map),
                )
            else:
                self._log.exception("live_game_champion_map_fetch_failed")

        entries_by_puuid: dict[str, list[dict]] = {}
        unique_puuids: list[str] = []
        seen: set[str] = set()
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            puuid = str(participant.get("puuid") or "").strip()
            if not puuid or puuid in seen:
                continue
            seen.add(puuid)
            unique_puuids.append(puuid)

        sem = asyncio.Semaphore(4)

        async def _fetch_entries_for_puuid(puuid: str) -> tuple[str, list[dict]]:
            async with sem:
                await asyncio.sleep(0.03 + random.random() * 0.04)
                try:
                    entries = await client.get_league_entries_by_puuid(platform, puuid)
                except httpx.HTTPStatusError as e:
                    self._log.warning(
                        "live_game_participant_rank_http_error",
                        status=e.response.status_code,
                        puuid=puuid,
                        platform=platform,
                    )
                    entries = []
                except Exception:
                    self._log.exception(
                        "live_game_participant_rank_fetch_failed",
                        puuid=puuid,
                        platform=platform,
                    )
                    entries = []
            cleaned = [entry for entry in entries if isinstance(entry, dict)]
            return puuid, cleaned

        fetched = await asyncio.gather(*(_fetch_entries_for_puuid(puuid) for puuid in unique_puuids))
        entries_by_puuid = {puuid: entries for puuid, entries in fetched}

        enriched_participants: list[dict] = []
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            row = dict(participant)
            champion_id = _safe_int(row.get("championId"))
            if champion_id is not None:
                champion_meta = champion_name_map.get(champion_id) or {}
                champion_key = str(champion_meta.get("key") or "").strip()
                champion_name = str(champion_meta.get("name") or "").strip()
                if champion_key:
                    row["championKey"] = champion_key
                if champion_name and not row.get("championName"):
                    row["championName"] = champion_name

            puuid = str(row.get("puuid") or "").strip()
            participant_entries = entries_by_puuid.get(puuid, [])
            row["soloRankedState"] = _ranked_state_from_entry(
                QUEUE_SOLO,
                next((entry for entry in participant_entries if str(entry.get("queueType") or "") == QUEUE_SOLO), None),
            )
            row["flexRankedState"] = _ranked_state_from_entry(
                QUEUE_FLEX,
                next((entry for entry in participant_entries if str(entry.get("queueType") or "") == QUEUE_FLEX), None),
            )
            row["rankedState"] = _select_ranked_state(participant_entries, queue_id)
            enriched_participants.append(row)

        payload["participants"] = enriched_participants
        return payload

    async def refresh(self, session: AsyncSession) -> dict[str, int]:
        settings = get_settings()
        if not settings.riot_api_key.strip():
            raise ValueError("missing_riot_api_key")

        players = await self._players_repo.get_all(session)
        targets = [p for p in players if p.active and p.puuid and p.platform]

        client = RiotClient(settings.riot_api_key)
        updated = 0
        skipped = 0
        errors = 0
        enriched_games_by_id: dict[str, dict] = {}

        try:
            for p in players:
                if not (p.active and p.puuid and p.platform):
                    skipped += 1
                    await self._repo.upsert_state(
                        session,
                        tracked_player_id=p.id,
                        platform=p.platform,
                        status="none",
                        game_id=None,
                        payload=None,
                    )
                    updated += 1
                    continue

                try:
                    game = await self._fetch_active_game_with_fallback(
                        client=client,
                        platform=p.platform,  # type: ignore[arg-type]
                        puuid=p.puuid,
                        player_id=str(p.id),
                    )
                    if game is None:
                        await self._repo.upsert_state(
                            session,
                            tracked_player_id=p.id,
                            platform=p.platform,
                            status="none",
                            game_id=None,
                            payload=None,
                        )
                        updated += 1
                        continue

                    game_id = str(game.get("gameId") or "")
                    payload = game
                    if game_id:
                        cached = enriched_games_by_id.get(game_id)
                        if cached is None:
                            cached = await self._enrich_live_game_payload(
                                game=game,
                                platform=p.platform,  # type: ignore[arg-type]
                                client=client,
                            )
                            enriched_games_by_id[game_id] = cached
                        payload = cached
                    queue_type = QUEUE_BY_ID.get(_safe_int(payload.get("gameQueueConfigId") or payload.get("queueId")))
                    if game_id and queue_type and p.puuid:
                        ranked_state = _tracked_player_ranked_state(payload, p.puuid, queue_type)
                        if ranked_state is not None:
                            await self._repo.upsert_ranked_snapshot(
                                session,
                                tracked_player_id=p.id,
                                platform=p.platform,
                                game_id=game_id,
                                queue_type=queue_type,
                                tier=ranked_state.get("tier"),
                                division=ranked_state.get("division"),
                                league_points=_safe_int(ranked_state.get("league_points")),
                                wins=_safe_int(ranked_state.get("wins")),
                                losses=_safe_int(ranked_state.get("losses")),
                            )
                    await self._repo.upsert_state(
                        session,
                        tracked_player_id=p.id,
                        platform=p.platform,
                        status="live",
                        game_id=game_id if game_id else None,
                        payload=payload,
                    )
                    updated += 1
                except httpx.HTTPStatusError as e:
                    errors += 1
                    self._log.error(
                        "live_game_fetch_http_error",
                        status=e.response.status_code,
                        player_id=str(p.id),
                        platform=p.platform,
                    )
                except Exception:
                    errors += 1
                    self._log.exception(
                        "live_game_refresh_failed",
                        player_id=str(p.id),
                        platform=p.platform,
                    )

            return {"updated": updated, "skipped": skipped, "errors": errors, "targets": len(targets)}
        finally:
            await client.aclose()

    async def list(self, session: AsyncSession, only_active: bool) -> list[LiveGameOut]:
        settings = get_settings()
        players = await self._players_repo.get_all(session)
        players_by_id = {str(p.id): p for p in players}
        tracked_puuids = {str(p.puuid or "").strip() for p in players if getattr(p, "puuid", None)}
        tracked_puuids.discard("")
        latest = await self._leaderboards_repo.get_latest_snapshots(session)
        snaps_by_player: dict[str, dict[str, RankedSnapshot]] = {}
        for snapshot in latest:
            player_snapshots = snaps_by_player.setdefault(str(snapshot.tracked_player_id), {})
            player_snapshots[snapshot.queue_type] = snapshot

        states = await self._repo.list_states(session)
        prediction_by_game_id: dict[str, dict] = {}
        game_payloads: dict[str, dict] = {}
        for state in states:
            if state.status != "live" or not state.game_id:
                continue
            payload = state.payload if isinstance(state.payload, dict) else None
            if payload is None or state.game_id in game_payloads:
                continue
            game_payloads[state.game_id] = payload

        if game_payloads:
            game_regions: dict[str, str] = {}
            for state in states:
                if state.status != "live" or not state.game_id:
                    continue
                player = players_by_id.get(str(state.tracked_player_id))
                region = str(getattr(player, "region", "") or "").strip().lower() if player is not None else ""
                if region and state.game_id not in game_regions:
                    game_regions[state.game_id] = region

            riot_client: RiotClient | None = None
            if settings.riot_api_key.strip():
                riot_client = RiotClient(settings.riot_api_key)
            try:
                tasks = [
                    self._compute_prediction_for_game(
                        session=session,
                        game_id=game_id,
                        payload=payload,
                        tracked_puuids=tracked_puuids,
                        riot_client=riot_client,
                        riot_region=game_regions.get(game_id),
                    )
                    for game_id, payload in game_payloads.items()
                ]
                predictions = await asyncio.gather(*tasks)
            finally:
                if riot_client is not None:
                    await riot_client.aclose()
            prediction_by_game_id = {
                game_id: prediction
                for game_id, prediction in zip(game_payloads.keys(), predictions, strict=False)
                if isinstance(prediction, dict)
            }

        out: list[LiveGameOut] = []
        for s in states:
            p = players_by_id.get(str(s.tracked_player_id))
            if p is None:
                continue
            if only_active and s.status != "live":
                continue
            player_snaps = snaps_by_player.get(str(p.id), {})
            out.append(
                LiveGameOut(
                    tracked_player_id=p.id,
                    puuid=p.puuid,
                    discord_display_name=p.discord_display_name,
                    game_name=p.game_name,
                    tag_line=p.tag_line,
                    platform=p.platform,
                    status=s.status,
                    game_id=s.game_id,
                    payload=s.payload,
                    fetched_at=s.fetched_at,
                    win_prediction=prediction_by_game_id.get(s.game_id) if s.game_id else None,
                    solo=_state_from_snapshot(QUEUE_SOLO, player_snaps.get(QUEUE_SOLO)),
                    flex=_state_from_snapshot(QUEUE_FLEX, player_snaps.get(QUEUE_FLEX)),
                )
            )
        return out
