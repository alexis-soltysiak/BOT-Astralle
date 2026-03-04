from __future__ import annotations

from app.features.scoring.engine import _compute_one_sync
from app.features.scoring.params import load_params


def _base_info() -> dict:
    return {
        "gameDuration": 1800,
        "teams": [
            {"teamId": 100, "objectives": {}},
            {"teamId": 200, "objectives": {}},
        ],
    }


def _base_participant() -> dict:
    return {
        "puuid": "player-1",
        "teamId": 100,
        "teamPosition": "TOP",
        "kills": 3,
        "deaths": 2,
        "assists": 4,
        "totalMinionsKilled": 150,
        "neutralMinionsKilled": 10,
        "goldEarned": 9000,
        "totalDamageDealtToChampions": 18000,
        "visionScore": 20,
        "champExperience": 10000,
        "totalDamageTaken": 12000,
        "damageDealtToObjectives": 3000,
        "turretTakedowns": 1,
        "challenges": {
            "maxCsAdvantageOnLaneOpponent": -12,
            "soloKills": 1,
            "turretPlatesTaken": 2,
            "laneMinionsFirst10Minutes": 70,
        },
    }


def test_vs_opponent_metrics_are_neutral_when_opponent_missing() -> None:
    params = load_params()
    participant = _base_participant()

    result = _compute_one_sync(
        params,
        participant,
        opponents={},
        team_sums={100: {"kills": 10.0, "dmg_dealt": 50000.0, "dmg_taken": 30000.0}},
        obj_by_team={100: {}},
        team_win_by_id={100: True, 200: False},
        info=_base_info(),
    )

    metrics = {metric["key"]: metric for metric in result["categories"]["vs_opponent"]["metrics"]}
    assert metrics["xp_diff"]["value"] == 0.0
    assert metrics["gold_diff"]["value"] == 0.0
    assert metrics["vision_diff"]["value"] == 0.0
    assert metrics["max_cs_diff"]["value"] == 0.0


def test_vs_opponent_metric_payload_keeps_signed_value() -> None:
    params = load_params()
    participant = _base_participant()
    opponent = {
        "puuid": "player-2",
        "teamId": 200,
        "teamPosition": "TOP",
        "goldEarned": 9500,
        "visionScore": 25,
        "champExperience": 11000,
    }

    result = _compute_one_sync(
        params,
        participant,
        opponents={"player-1": opponent},
        team_sums={100: {"kills": 10.0, "dmg_dealt": 50000.0, "dmg_taken": 30000.0}},
        obj_by_team={100: {}},
        team_win_by_id={100: True, 200: False},
        info=_base_info(),
    )

    metrics = {metric["key"]: metric for metric in result["categories"]["vs_opponent"]["metrics"]}
    assert metrics["xp_diff"]["value"] == -1000.0
    assert metrics["gold_diff"]["value"] == -500.0
    assert metrics["vision_diff"]["value"] == -5.0
    assert metrics["max_cs_diff"]["value"] == -12.0
