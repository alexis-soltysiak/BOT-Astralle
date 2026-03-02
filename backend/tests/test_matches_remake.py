from __future__ import annotations

from app.features.matches.service import _is_remake_match_payload


def test_is_remake_match_payload_detects_early_surrender() -> None:
    payload = {
        "info": {
            "participants": [
                {"puuid": "a", "gameEndedInEarlySurrender": False},
                {"puuid": "b", "gameEndedInEarlySurrender": True},
            ]
        }
    }

    assert _is_remake_match_payload(payload) is True


def test_is_remake_match_payload_false_when_no_early_surrender() -> None:
    payload = {
        "info": {
            "participants": [
                {"puuid": "a", "gameEndedInEarlySurrender": False},
                {"puuid": "b"},
            ]
        }
    }

    assert _is_remake_match_payload(payload) is False
