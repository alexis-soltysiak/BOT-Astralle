from app.features.matches.embeds import build_match_finished_embed


def test_build_match_finished_embed_lists_all_tracked_players_in_same_match() -> None:
    summary = {
        "riot_match_id": "EUW1_123",
        "region": "europe",
        "queue_id": 420,
        "game_mode": "CLASSIC",
        "ranked_queue_type": "RANKED_SOLO_5x5",
        "game_duration": 1800,
        "game_end_ts": 1700000000000,
        "participants": [
            {
                "puuid": "puuid-b",
                "team_id": 100,
                "riot_id_game_name": "Beta",
                "riot_id_tag_line": "EUW",
                "champion_name": "Ahri",
                "kills": 8,
                "deaths": 3,
                "assists": 6,
                "win": True,
                "payload": {
                    "teamPosition": "MIDDLE",
                    "totalMinionsKilled": 180,
                    "neutralMinionsKilled": 10,
                },
            },
            {
                "puuid": "puuid-a",
                "team_id": 100,
                "riot_id_game_name": "Alpha",
                "riot_id_tag_line": "EUW",
                "champion_name": "LeeSin",
                "kills": 4,
                "deaths": 5,
                "assists": 12,
                "win": True,
                "payload": {
                    "teamPosition": "JUNGLE",
                    "totalMinionsKilled": 30,
                    "neutralMinionsKilled": 140,
                },
            },
        ],
        "scores": [
            {
                "puuid": "puuid-b",
                "role": "MID",
                "final_score": 8.0,
                "final_grade": "A",
                "categories": {},
                "rank_delta_lp": 18,
                "rank_after": "Gold I - 18 LP",
            },
            {
                "puuid": "puuid-a",
                "role": "JUNGLE",
                "final_score": 7.5,
                "final_grade": "A-",
                "categories": {},
                "rank_delta_lp": 18,
                "rank_after": "Gold I - 18 LP",
            },
        ],
    }
    tracked_by_puuid = {
        "puuid-a": {"game_name": "Alpha", "tag_line": "EUW"},
        "puuid-b": {"game_name": "Beta", "tag_line": "EUW"},
    }

    embed, file, view = build_match_finished_embed(summary, tracked_by_puuid, resolver=None)

    assert embed.author.name == "Alpha#EUW"
    tracked_field = next(field for field in embed.fields if field.name == "Tracked players")
    assert "Alpha#EUW" in tracked_field.value
    assert "Beta#EUW" in tracked_field.value
    assert file is None
    assert view is not None


def test_build_match_finished_embed_single_tracked_player_keeps_category_buttons() -> None:
    summary = {
        "riot_match_id": "EUW1_456",
        "region": "europe",
        "queue_id": 420,
        "game_mode": "CLASSIC",
        "ranked_queue_type": "RANKED_SOLO_5x5",
        "game_duration": 1800,
        "game_end_ts": 1700000000000,
        "participants": [
            {
                "puuid": "puuid-a",
                "team_id": 100,
                "riot_id_game_name": "Alpha",
                "riot_id_tag_line": "EUW",
                "champion_name": "Ahri",
                "kills": 10,
                "deaths": 3,
                "assists": 8,
                "win": True,
                "payload": {
                    "teamPosition": "MIDDLE",
                    "totalMinionsKilled": 180,
                    "neutralMinionsKilled": 20,
                },
            },
        ],
        "scores": [
            {
                "puuid": "puuid-a",
                "role": "MID",
                "final_score": 8.6,
                "final_grade": "S-",
                "categories": {"global": {"rank": 1}},
                "rank_delta_lp": 20,
                "rank_after": "Gold I - 40 LP",
            },
        ],
    }
    tracked_by_puuid = {"puuid-a": {"game_name": "Alpha", "tag_line": "EUW"}}

    embed, file, view = build_match_finished_embed(summary, tracked_by_puuid, resolver=None)

    assert embed.author.name == "Alpha#EUW"
    assert file is not None
    assert view is not None
    labels = [getattr(child, "label", "") for child in view.children]
    assert "Global" in labels
