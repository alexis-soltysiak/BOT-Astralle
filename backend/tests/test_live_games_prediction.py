from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.features.live_games import service as live_games_service
from app.features.live_games.service import LiveGamesService


class _Repo:
    async def list_states(self, session):  # type: ignore[no-untyped-def]
        return []


class _PlayersRepo:
    async def get_all(self, session):  # type: ignore[no-untyped-def]
        return []


class _LeaderboardsRepo:
    async def get_latest_snapshots(self, session):  # type: ignore[no-untyped-def]
        return []


def test_recent_weighted_score_prioritizes_last_three() -> None:
    # Most recent score is index 0.
    values = [100.0, 100.0, 100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    weighted = live_games_service._recent_weighted_score(values)

    assert weighted is not None
    assert weighted > 60.0


def test_lp_total_from_ranked_state_supports_division_and_apex() -> None:
    gold_two = live_games_service._lp_total_from_ranked_state(
        {"tier": "GOLD", "division": "II", "league_points": 80}
    )
    challenger = live_games_service._lp_total_from_ranked_state(
        {"tier": "CHALLENGER", "division": "I", "league_points": 550}
    )

    assert gold_two == 3 * 400 + 200 + 80
    assert challenger == 9 * 400 + 550


@pytest.mark.asyncio
async def test_compute_prediction_for_game_returns_teams_and_players(monkeypatch) -> None:
    service = LiveGamesService(_Repo(), _PlayersRepo(), _LeaderboardsRepo())

    recent_by_puuid = {
        "blue-1": [82.0, 80.0, 78.0],
        "blue-2": [70.0, 72.0, 73.0],
        "red-1": [60.0, 62.0, 58.0],
        "red-2": [55.0, 57.0, 54.0],
    }

    async def _fake_recent_scores(self, session, puuid, limit=10):  # type: ignore[no-untyped-def]
        _ = session
        _ = limit
        return recent_by_puuid.get(puuid, [])

    monkeypatch.setattr(LiveGamesService, "_recent_scores_for_puuid", _fake_recent_scores)

    payload = {
        "participants": [
            {
                "puuid": "blue-1",
                "teamId": 100,
                "riotId": "Blue1#EUW",
                "rankedState": {"tier": "PLATINUM", "division": "II", "league_points": 75},
            },
            {
                "puuid": "blue-2",
                "teamId": 100,
                "riotId": "Blue2#EUW",
                "rankedState": {"tier": "GOLD", "division": "I", "league_points": 90},
            },
            {
                "puuid": "red-1",
                "teamId": 200,
                "riotId": "Red1#EUW",
                "rankedState": {"tier": "GOLD", "division": "III", "league_points": 20},
            },
            {
                "puuid": "red-2",
                "teamId": 200,
                "riotId": "Red2#EUW",
                "rankedState": {"tier": "SILVER", "division": "I", "league_points": 40},
            },
        ]
    }

    prediction = await service._compute_prediction_for_game(session=None, game_id="game-1", payload=payload)

    assert prediction is not None
    assert prediction["model_version"] == "v1_weighted10_elo_lp"
    assert len(prediction["players"]) == 4
    assert prediction["team_blue"]["win_probability"] > prediction["team_red"]["win_probability"]
    assert 0.05 <= prediction["team_blue"]["win_probability"] <= 0.95
