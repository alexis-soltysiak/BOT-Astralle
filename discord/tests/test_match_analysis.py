from app.features.matches.analysis import _build_prompt, _normalize_analysis_payload
from app.features.matches.embeds import build_match_analysis_context, should_request_match_analysis


def test_should_request_match_analysis_for_ranked_queues() -> None:
    assert should_request_match_analysis({"queue_id": 420}) is True
    assert should_request_match_analysis({"queue_id": 440}) is True
    assert should_request_match_analysis({"queue_id": 450}) is False


def test_build_match_analysis_context_contains_ranked_details() -> None:
    summary = {
        "riot_match_id": "EUW1_123",
        "queue_id": 420,
        "ranked_queue_type": "RANKED_SOLO_5x5",
        "game_mode": "CLASSIC",
        "game_duration": 1800,
        "participants": [
            {
                "puuid": "tracked-puuid",
                "team_id": 100,
                "riot_id_game_name": "Astral",
                "riot_id_tag_line": "EUW",
                "champion_name": "Ahri",
                "kills": 10,
                "deaths": 2,
                "assists": 8,
                "win": True,
                "payload": {
                    "teamPosition": "MIDDLE",
                    "totalMinionsKilled": 180,
                    "neutralMinionsKilled": 12,
                    "summoner1Id": 4,
                    "summoner2Id": 14,
                    "item0": 3157,
                },
            },
            {
                "puuid": "ally",
                "team_id": 100,
                "kills": 20,
                "deaths": 5,
                "assists": 10,
                "payload": {},
            },
        ],
        "scores": [
            {
                "puuid": "tracked-puuid",
                "role": "MID",
                "final_score": 88.3,
                "rank_before": "Gold II - 80 LP",
                "rank_after": "Gold I - 15 LP",
                "rank_delta_lp": 35,
                "categories": {
                    "global": {
                        "rank": 1,
                        "total_points": 18.2,
                        "metrics": [
                            {"label": "KDA", "value": 9.0, "points": 4.5},
                        ],
                    },
                    "team": {
                        "rank": 2,
                        "total_points": 12.1,
                        "metrics": [
                            {"label": "KP", "value": 64.3, "points": 2.3},
                        ],
                    },
                },
            }
        ],
    }
    tracked = {
        "tracked-puuid": {
            "discord_display_name": "Alex",
            "game_name": "Astral",
            "tag_line": "EUW",
        }
    }

    context = build_match_analysis_context(summary, tracked)

    assert context is not None
    assert context["player_name"] == "Alex"
    assert context["queue"] == "SoloQ"
    assert context["role"] == "MID"
    assert context["kp"] == "60.0%"
    assert context["rank_delta_lp"] == 35
    assert context["final_rank"] == 1
    assert len(context["category_details"]) == 2


def test_prompt_and_normalization() -> None:
    context = {
        "player_name": "Alex",
        "riot_match_id": "EUW1_123",
        "queue": "SoloQ",
        "ranked_queue_type": "RANKED_SOLO_5x5",
        "champion": "Ahri",
        "role": "MID",
        "result": "win",
        "duration": "30m 00s",
        "kda": "10/2/8",
        "kp": "64.3%",
        "cs": "192 (6.4/min)",
        "final_score": 88.3,
        "final_rank": 1,
        "lp_line": "+35 LP | I 15 LP",
        "rank_before": "Gold II - 80 LP",
        "rank_after": "Gold I - 15 LP",
        "rank_delta_lp": 35,
        "notes_summary": "Global: 1/10",
        "spells": [4, 14],
        "items": [3157],
        "category_details": [{"label": "Global", "rank": 1, "total_points": 18.2, "metrics": []}],
    }
    prompt = _build_prompt(context)

    assert "Joueur: Alex" in prompt
    assert "Schema JSON obligatoire:" in prompt
    assert "Score final: 88.3/100" in prompt
    assert 'exactement 3 points' in prompt
    assert "priorite lane" in prompt
    normalized = _normalize_analysis_payload(
        """
        {
          "headline": "🎯 Bonne game de tempo",
          "summary": "🧠 Tu as bien converti ton avance.",
          "strengths": ["✅ Bons timings de trade", "💥 Bonne pression mid", "🧭 Bons roams", "➕ Extra"],
          "improvements": ["⚠️ Trop de greed avant reset", "🧱 Mieux timer recalls", "➖ Extra"],
          "next_steps": ["📍 Push puis ward river", "🛒 Reset sur spike item", "🎯 Punir flash mid"],
          "key_focus": "📌 Stabiliser tes resets",
          "confidence": "high"
        }
        """
    , context)
    assert normalized is not None
    assert normalized["headline"] == "🎯 Bonne game de tempo"
    assert normalized["confidence"] == "high"
    assert normalized["strengths"][0] == "✅ Bons timings de trade"
    assert len(normalized["strengths"]) == 3
    assert len(normalized["improvements"]) == 2
