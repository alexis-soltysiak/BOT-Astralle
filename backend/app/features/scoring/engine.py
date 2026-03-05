from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass

from app.features.scoring.params import load_params


@dataclass(frozen=True)
class MetricLine:
    key: str
    label: str
    value: float
    points: float


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _round1(x: float) -> float:
    return float(f"{x:.1f}")


def _round2(x: float) -> float:
    return float(f"{x:.2f}")


def _grade_from_thresholds(value: float, thresholds: list[dict]) -> str:
    for t in thresholds:
        if value >= float(t["min"]):
            return str(t["grade"])
    return str(thresholds[-1]["grade"]) if thresholds else "F"


def _grade_from_rank(rank: int, mapping: list[dict]) -> str:
    for m in mapping:
        if rank <= int(m["rank_max"]):
            return str(m["grade"])
    return "F"


def _normalize_role(team_position: str | None) -> str:
    v = (team_position or "").upper().strip()
    if v in ("TOP",):
        return "TOP"
    if v in ("JUNGLE",):
        return "JUNGLE"
    if v in ("MIDDLE", "MID"):
        return "MID"
    if v in ("BOTTOM", "BOT", "ADC"):
        return "ADC"
    if v in ("UTILITY", "SUPPORT"):
        return "SUPPORT"
    return "UNKNOWN"


def _extract_challenges(p: dict) -> dict:
    c = p.get("challenges")
    return c if isinstance(c, dict) else {}


def _safe_num(x, default: float = 0.0) -> float:
    if x is None:
        return default
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x))
    except Exception:
        return default


def _points(cfg: dict, role: str, value: float) -> float:
    kind = str(cfg.get("kind") or "linear")

    if kind == "role_linear":
        by = cfg.get("by_role") or {}
        c = by.get(role) or by.get("DEFAULT") or {}
        a = _safe_num(c.get("a"))
        b = _safe_num(c.get("b"))
        lo = _safe_num(c.get("min"), -1e9)
        hi = _safe_num(c.get("max"), 1e9)
        return _round1(_clamp(a * value + b, lo, hi))

    if kind == "role_clamp_linear":
        by = cfg.get("by_role") or {}
        c = by.get(role) or by.get("DEFAULT") or {}
        a = _safe_num(c.get("a"))
        b = _safe_num(c.get("b"))
        lo = _safe_num(c.get("min"), -1e9)
        hi = _safe_num(c.get("max"), 1e9)
        return _round1(_clamp(a * value + b, lo, hi))

    if kind == "clamp_linear":
        a = _safe_num(cfg.get("a"))
        b = _safe_num(cfg.get("b"))
        lo = _safe_num(cfg.get("min"), -1e9)
        hi = _safe_num(cfg.get("max"), 1e9)
        return _round1(_clamp(a * value + b, lo, hi))

    if kind == "linear":
        a = _safe_num(cfg.get("a"))
        b = _safe_num(cfg.get("b"))
        lo = _safe_num(cfg.get("min"), -1e9)
        hi = _safe_num(cfg.get("max"), 1e9)
        return _round1(_clamp(a * value + b, lo, hi))

    if kind == "binary":
        t = _safe_num(cfg.get("true"))
        f = _safe_num(cfg.get("false"))
        return _round1(t if value > 0 else f)

    if kind == "cap_threshold":
        thr = _safe_num(cfg.get("threshold"), 1.0)
        mp = _safe_num(cfg.get("max_points"))
        if thr <= 0:
            return _round1(mp)
        x = _clamp(value / thr, 0.0, 1.0)
        return _round1(mp * x)

    if kind == "zero_penalty":
        pen = _safe_num(cfg.get("penalty"), -1.0)
        return _round1(pen if abs(value) < 1e-9 else 0.0)

    return 0.0


def _team_objectives(info: dict) -> dict[int, dict]:
    teams = info.get("teams") or []
    out: dict[int, dict] = {}
    for t in teams:
        team_id = int(_safe_num(t.get("teamId"), 0))
        obj = t.get("objectives") or {}
        out[team_id] = obj if isinstance(obj, dict) else {}
    return out


def _objective_kills(obj: dict, key: str) -> int:
    x = obj.get(key)
    if isinstance(x, dict):
        return int(_safe_num(x.get("kills"), 0))
    return 0


def _find_opponents(parts: list[dict]) -> dict[str, dict]:
    by_team_role: dict[tuple[int, str], dict] = {}
    for p in parts:
        team_id = int(_safe_num(p.get("teamId"), 0))
        role = _normalize_role(p.get("teamPosition") or p.get("individualPosition"))
        puuid = str(p.get("puuid") or "")
        if not puuid:
            continue
        if role == "UNKNOWN":
            continue
        by_team_role[(team_id, role)] = p

    opponents: dict[str, dict] = {}
    for p in parts:
        puuid = str(p.get("puuid") or "")
        if not puuid:
            continue
        team_id = int(_safe_num(p.get("teamId"), 0))
        role = _normalize_role(p.get("teamPosition") or p.get("individualPosition"))
        other_team = 200 if team_id == 100 else 100
        opp = by_team_role.get((other_team, role))
        if opp:
            opponents[puuid] = opp
    return opponents


def _team_sums(parts: list[dict]) -> dict[int, dict]:
    sums: dict[int, dict] = {}
    for p in parts:
        team_id = int(_safe_num(p.get("teamId"), 0))
        s = sums.setdefault(team_id, {"kills": 0.0, "dmg_dealt": 0.0, "dmg_taken": 0.0})
        s["kills"] += _safe_num(p.get("kills"), 0)
        s["dmg_dealt"] += _safe_num(p.get("totalDamageDealtToChampions"), 0)
        s["dmg_taken"] += _safe_num(p.get("totalDamageTaken"), 0)
    return sums


def _team_win_by_id(info: dict) -> dict[int, bool]:
    out: dict[int, bool] = {}
    teams = info.get("teams") or []
    for t in teams:
        team_id = int(_safe_num(t.get("teamId"), 0))
        out[team_id] = bool(t.get("win") is True)
    return out


def _category_component(rank: int, n: int, raw: float, raw_min: float, raw_max: float, alpha: float) -> float:
    if n <= 1:
        rank_score = 0.5
    else:
        rank_score = (n - rank) / (n - 1)
    if raw_max - raw_min < 1e-9:
        raw_score = 0.5
    else:
        raw_score = (raw - raw_min) / (raw_max - raw_min)
    return alpha * rank_score + (1.0 - alpha) * raw_score


async def compute_match_scoring(match_payload: dict) -> list[dict]:
    params = load_params()
    info = match_payload.get("info") or {}
    parts = info.get("participants") or []
    if not isinstance(parts, list):
        return []

    obj_by_team = _team_objectives(info)
    team_sums = _team_sums(parts)
    team_win_by_id = _team_win_by_id(info)
    opponents = _find_opponents(parts)

    async def compute_one(p: dict) -> dict:
        return await asyncio.to_thread(
            _compute_one_sync,
            params,
            p,
            opponents,
            team_sums,
            obj_by_team,
            team_win_by_id,
            info,
        )

    results = await asyncio.gather(*[compute_one(p) for p in parts if str(p.get("puuid") or "")])
    results = [r for r in results if r.get("puuid")]
    return _finalize_ranks_and_scores(params, results)


def _compute_one_sync(
    params: dict,
    p: dict,
    opponents: dict,
    team_sums: dict,
    obj_by_team: dict,
    team_win_by_id: dict,
    info: dict,
) -> dict:
    metrics_cfg = params["metrics"]
    grade_rank_map = params["category_grade_by_rank"]
    alpha = float(params["final"]["alpha_rank_vs_raw"])

    puuid = str(p.get("puuid") or "")
    team_id = int(_safe_num(p.get("teamId"), 0))
    role = _normalize_role(p.get("teamPosition") or p.get("individualPosition"))

    duration_s = _safe_num(info.get("gameDuration"), _safe_num(info.get("gameEndTimestamp"), 0) / 1000.0)
    minutes = max(1.0, duration_s / 60.0)

    ch = _extract_challenges(p)

    kills = _safe_num(p.get("kills"))
    deaths = _safe_num(p.get("deaths"))
    assists = _safe_num(p.get("assists"))

    cs = _safe_num(p.get("totalMinionsKilled")) + _safe_num(p.get("neutralMinionsKilled"))
    cs_per_min = cs / minutes

    gold_per_min = _safe_num(p.get("goldEarned")) / minutes
    dmg_per_min = _safe_num(p.get("totalDamageDealtToChampions")) / minutes
    vision_per_min = _safe_num(p.get("visionScore")) / minutes

    first_blood = 1.0 if (p.get("firstBloodKill") is True or p.get("firstBloodAssist") is True) else 0.0

    opp = opponents.get(puuid) or {}
    if opp:
        # Riot "vs opponent" values shown in post-game are max lane advantages.
        # Fall back to end-of-game deltas when challenge fields are absent.
        xp_diff = _safe_num(
            ch.get("maxXpAdvantageOnLaneOpponent"),
            _safe_num(p.get("champExperience")) - _safe_num(opp.get("champExperience")),
        )
        gold_diff = _safe_num(
            ch.get("maxGoldAdvantageOnLaneOpponent"),
            _safe_num(p.get("goldEarned")) - _safe_num(opp.get("goldEarned")),
        )
        vision_diff = _safe_num(p.get("visionScore")) - _safe_num(opp.get("visionScore"))
        max_cs_diff = _safe_num(ch.get("maxCsAdvantageOnLaneOpponent"))
    else:
        xp_diff = _safe_num(ch.get("maxXpAdvantageOnLaneOpponent"))
        gold_diff = _safe_num(ch.get("maxGoldAdvantageOnLaneOpponent"))
        vision_diff = 0.0
        max_cs_diff = _safe_num(ch.get("maxCsAdvantageOnLaneOpponent"))

    t_kills = _safe_num(team_sums.get(team_id, {}).get("kills"), 0.0)
    kp = 0.0 if t_kills <= 0 else 100.0 * (kills + assists) / t_kills

    t_dmg_dealt = _safe_num(team_sums.get(team_id, {}).get("dmg_dealt"), 0.0)
    dmg_dealt_pct = 0.0 if t_dmg_dealt <= 0 else 100.0 * _safe_num(p.get("totalDamageDealtToChampions")) / t_dmg_dealt

    t_dmg_taken = _safe_num(team_sums.get(team_id, {}).get("dmg_taken"), 0.0)
    dmg_taken_pct = 0.0 if t_dmg_taken <= 0 else 100.0 * _safe_num(p.get("totalDamageTaken")) / t_dmg_taken

    obj = obj_by_team.get(team_id, {})
    dragons = _objective_kills(obj, "dragon")
    barons = _objective_kills(obj, "baron")
    rift = _objective_kills(obj, "riftHerald")
    grubs = _objective_kills(obj, "horde")

    dmg_to_obj = _safe_num(p.get("damageDealtToObjectives"))
    epic_steals = _safe_num(ch.get("epicMonsterSteals"))

    global_lines: list[MetricLine] = []
    for key, val in (
        ("kills", kills),
        ("deaths", deaths),
        ("assists", assists),
        ("cs_per_min", cs_per_min),
        ("gold_per_min", gold_per_min),
        ("dmg_per_min", dmg_per_min),
        ("vision_per_min", vision_per_min),
        ("first_blood", first_blood),
    ):
        cfg = metrics_cfg["global"][key]
        pts = _points(cfg, role, float(val))
        global_lines.append(MetricLine(key=key, label=str(cfg["label"]), value=_round1(float(val)), points=pts))

    opp_lines: list[MetricLine] = []
    for key, val in (
        ("xp_diff", xp_diff),
        ("gold_diff", gold_diff),
        ("vision_diff", vision_diff),
        ("max_cs_diff", max_cs_diff),
    ):
        cfg = metrics_cfg["vs_opponent"][key]
        pts = _points(cfg, role, float(val))
        opp_lines.append(MetricLine(key=key, label=str(cfg["label"]), value=_round1(float(val)), points=pts))

    obj_lines: list[MetricLine] = []
    for key, val in (
        ("rift_herald", rift),
        ("dragons", dragons),
        ("barons", barons),
        ("grubs", grubs),
        ("dmg_to_objectives", dmg_to_obj),
        ("epic_steals", epic_steals),
    ):
        cfg = metrics_cfg["objectives"][key]
        pts = _points(cfg, role, float(val))
        obj_lines.append(MetricLine(key=key, label=str(cfg["label"]), value=_round1(float(val)), points=pts))

    team_lines: list[MetricLine] = []
    for key, val in (
        ("kill_participation", kp),
        ("damage_taken_pct", dmg_taken_pct),
        ("damage_dealt_pct", dmg_dealt_pct),
    ):
        cfg = metrics_cfg["team"][key]
        pts = _points(cfg, role, float(val))
        team_lines.append(MetricLine(key=key, label=str(cfg["label"]), value=_round1(float(val)), points=pts))

    role_cfg = metrics_cfg["role"].get(role) or {}
    role_lines: list[MetricLine] = []

    if role == "TOP" or role == "MID" or role == "ADC":
        solo_kills = _safe_num(ch.get("soloKills"))
        plates = _safe_num(ch.get("turretPlatesTaken"))
        cs10 = _safe_num(ch.get("laneMinionsFirst10Minutes"))
        turrets = _safe_num(p.get("turretTakedowns"))

        for key, val in (
            ("solo_kills", solo_kills),
            ("turret_plates", plates),
            ("cs_at_10", cs10),
            ("turrets", turrets),
        ):
            cfg = role_cfg[key]
            pts = _points(cfg, role, float(val))
            role_lines.append(MetricLine(key=key, label=str(cfg["label"]), value=_round1(float(val)), points=pts))

    elif role == "JUNGLE":
        initial_crabs = _safe_num(ch.get("initialCrabCount"))
        scuttle = _safe_num(ch.get("scuttleCrabKills"))
        jcs10 = _safe_num(ch.get("jungleCsBefore10Minutes"))
        pick = _safe_num(ch.get("pickKillWithAlly"))

        for key, val in (
            ("initial_crabs", initial_crabs),
            ("scuttle_crabs", scuttle),
            ("jungle_cs_at_10", jcs10),
            ("pick_kill_with_ally", pick),
        ):
            cfg = role_cfg[key]
            pts = _points(cfg, role, float(val))
            role_lines.append(MetricLine(key=key, label=str(cfg["label"]), value=_round1(float(val)), points=pts))

    elif role == "SUPPORT":
        control = _safe_num(p.get("visionWardsBoughtInGame"))
        wk = _safe_num(p.get("wardsKilled"))
        wp = _safe_num(p.get("wardsPlaced"))
        pick = _safe_num(ch.get("pickKillWithAlly"))
        save = _safe_num(ch.get("saveAllyFromDeath"))

        for key, val in (
            ("control_wards", control),
            ("wards_killed", wk),
            ("wards_placed", wp),
            ("pick_kill_with_ally", pick),
            ("save_ally", save),
        ):
            cfg = role_cfg[key]
            pts = _points(cfg, role, float(val))
            role_lines.append(MetricLine(key=key, label=str(cfg["label"]), value=_round1(float(val)), points=pts))

    def tot(lines: list[MetricLine]) -> float:
        return _round2(sum(l.points for l in lines))

    cat = {
        "global": {"total_points": tot(global_lines), "rank": 0, "grade": "", "metrics": [l.__dict__ for l in global_lines]},
        "vs_opponent": {"total_points": tot(opp_lines), "rank": 0, "grade": "", "metrics": [l.__dict__ for l in opp_lines]},
        "objectives": {"total_points": tot(obj_lines), "rank": 0, "grade": "", "metrics": [l.__dict__ for l in obj_lines]},
        "team": {"total_points": tot(team_lines), "rank": 0, "grade": "", "metrics": [l.__dict__ for l in team_lines]},
        "role": {"role": role, "total_points": tot(role_lines), "rank": 0, "grade": "", "metrics": [l.__dict__ for l in role_lines]}
    }

    return {
        "puuid": puuid,
        "role": role,
        "team_id": team_id,
        "won": bool(team_win_by_id.get(team_id, False)),
        "categories": cat,
        "final_score": 0.0,
        "final_grade": "F",
        "_alpha": alpha,
        "_grade_rank_map": grade_rank_map
    }


def _finalize_ranks_and_scores(params: dict, results: list[dict]) -> list[dict]:
    weights = params["final"]["weights"]
    alpha = float(params["final"]["alpha_rank_vs_raw"])
    grade_rank_map = params["category_grade_by_rank"]
    final_thresholds = params["final"]["grade_thresholds"]

    categories = ["global", "vs_opponent", "objectives", "team", "role"]

    for cat in categories:
        arr = [(r["puuid"], float(r["categories"][cat]["total_points"])) for r in results]
        arr_sorted = sorted(arr, key=lambda x: x[1], reverse=True)

        raw_vals = [x[1] for x in arr_sorted]
        raw_min = min(raw_vals) if raw_vals else 0.0
        raw_max = max(raw_vals) if raw_vals else 0.0
        n = len(arr_sorted)

        rank_by_puuid: dict[str, int] = {}
        for i, (puuid, _) in enumerate(arr_sorted, start=1):
            rank_by_puuid[puuid] = i

        for r in results:
            puuid = r["puuid"]
            rk = rank_by_puuid.get(puuid, n)
            r["categories"][cat]["rank"] = rk
            r["categories"][cat]["grade"] = _grade_from_rank(rk, grade_rank_map)

        for r in results:
            puuid = r["puuid"]
            raw = float(r["categories"][cat]["total_points"])
            rk = int(r["categories"][cat]["rank"])
            comp = _category_component(rk, n, raw, raw_min, raw_max, alpha)
            r["categories"][cat]["score_0_100"] = _round2(100.0 * comp)

    wsum = sum(float(weights.get(c, 1.0)) for c in categories)
    if wsum <= 0:
        wsum = 1.0

    for r in results:
        s = 0.0
        for c in categories:
            w = float(weights.get(c, 1.0))
            s += w * float(r["categories"][c]["score_0_100"])
        final = s / wsum
        base_final = _round2(_clamp(final, 0.0, 100.0))
        r["base_final_score"] = base_final
        r["final_score"] = base_final

    calibration = params.get("calibration")
    if isinstance(calibration, dict) and calibration.get("enabled") is True:
        _apply_v2_calibration(results, calibration)

    for r in results:
        r["final_score"] = _round2(_clamp(float(r.get("final_score") or 0.0), 0.0, 100.0))
        r["final_grade"] = _grade_from_thresholds(float(r["final_score"]), final_thresholds)

    return results


def _apply_v2_calibration(results: list[dict], calibration: dict) -> None:
    if not results:
        return

    by_team: dict[int, list[dict]] = {}
    by_team_role: dict[tuple[int, str], dict] = {}
    for r in results:
        team_id = int(_safe_num(r.get("team_id"), 0))
        role = str(r.get("role") or "UNKNOWN")
        by_team.setdefault(team_id, []).append(r)
        by_team_role[(team_id, role)] = r

    team_avg: dict[int, float] = {}
    for team_id, rows in by_team.items():
        vals = [float(x.get("base_final_score") or 0.0) for x in rows]
        team_avg[team_id] = sum(vals) / max(1, len(vals))

    duel_cfg = calibration.get("role_duel") or {}
    lobby_cfg = calibration.get("lobby_difficulty") or {}
    rebase_cfg = calibration.get("game_rebase") or {}

    duel_max = _safe_num(duel_cfg.get("max_abs_bonus"), 0.0)
    duel_w_role = _safe_num(duel_cfg.get("role_score_weight"), 0.0)
    duel_w_vs = _safe_num(duel_cfg.get("vs_opponent_weight"), 0.0)

    lobby_max = _safe_num(lobby_cfg.get("max_abs_bonus"), 0.0)
    lobby_scale = max(1e-9, _safe_num(lobby_cfg.get("team_avg_diff_scale"), 15.0))

    rebase_max = _safe_num(rebase_cfg.get("max_abs_bonus"), 0.0)
    rebase_scale = max(1e-9, _safe_num(rebase_cfg.get("player_vs_team_scale"), 18.0))
    win_bonus = _safe_num(rebase_cfg.get("win_bonus"), 0.0)
    loss_bonus = _safe_num(rebase_cfg.get("loss_bonus"), 0.0)

    stretch_cfg = calibration.get("final_stretch") or {}
    stretch_enabled = bool(stretch_cfg.get("enabled") is True)
    stretch_slope = _safe_num(stretch_cfg.get("slope"), 1.0)

    for r in results:
        team_id = int(_safe_num(r.get("team_id"), 0))
        role = str(r.get("role") or "UNKNOWN")
        other_team = 200 if team_id == 100 else 100

        base = float(r.get("base_final_score") or 0.0)
        role_score = float(r.get("categories", {}).get("role", {}).get("score_0_100") or 50.0)
        vs_score = float(r.get("categories", {}).get("vs_opponent", {}).get("score_0_100") or 50.0)

        role_duel_bonus = 0.0
        opp = by_team_role.get((other_team, role))
        if opp is not None and duel_max > 0:
            role_component = (role_score - 50.0) / 50.0
            vs_component = (vs_score - 50.0) / 50.0
            duel_power = duel_w_role * role_component + duel_w_vs * vs_component
            role_duel_bonus = _clamp(duel_power * duel_max, -duel_max, duel_max)

        own_team_avg = float(team_avg.get(team_id, 50.0))
        enemy_team_avg = float(team_avg.get(other_team, own_team_avg))
        diff_norm = _clamp((enemy_team_avg - own_team_avg) / lobby_scale, -1.0, 1.0)
        perf_norm = _clamp((base - 50.0) / 50.0, -1.0, 1.0)
        lobby_bonus = lobby_max * diff_norm * perf_norm

        contrib_norm = _clamp((base - own_team_avg) / rebase_scale, -1.0, 1.0)
        outcome_bonus = win_bonus if bool(r.get("won") is True) else loss_bonus
        rebase_bonus = _clamp(rebase_max * contrib_norm + outcome_bonus, -rebase_max, rebase_max)

        adjusted = base + role_duel_bonus + lobby_bonus + rebase_bonus
        if stretch_enabled:
            adjusted = 50.0 + stretch_slope * (adjusted - 50.0)

        r["adjustments"] = {
            "role_duel_bonus": _round2(role_duel_bonus),
            "lobby_difficulty_bonus": _round2(lobby_bonus),
            "game_rebase_bonus": _round2(rebase_bonus),
        }
        r["final_score"] = _round2(_clamp(adjusted, 0.0, 100.0))
