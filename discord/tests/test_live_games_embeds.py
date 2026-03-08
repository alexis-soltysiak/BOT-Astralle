from __future__ import annotations

from app.features.live_games.embeds import build_live_games_embeds


def test_build_live_games_embeds_includes_team_win_percentages() -> None:
    rows = [
        {
            "game_id": "123",
            "game_name": "Alpha",
            "tag_line": "EUW",
            "puuid": "tracked-1",
            "discord_display_name": "Alpha",
            "payload": {
                "gameQueueConfigId": 420,
                "participants": [
                    {"puuid": "tracked-1", "teamId": 100, "riotId": "Alpha#EUW", "championName": "Ahri"},
                    {"puuid": "p2", "teamId": 200, "riotId": "Beta#EUW", "championName": "Lux"},
                ],
            },
            "solo": {"tier": "GOLD", "division": "II", "league_points": 50},
            "flex": {},
            "fetched_at": "2026-03-07T12:00:00+00:00",
            "win_prediction": {
                "team_blue": {"win_probability": 0.623},
                "team_red": {"win_probability": 0.377},
            },
        }
    ]

    embeds = build_live_games_embeds(
        rows,
        role_emoji_fn=lambda role: "",
        champ_emoji_fn=lambda champion: "",
        rank_emoji_fn=lambda tier: "",
        live_emoji_fn=lambda: "",
        refresh_interval_seconds=60,
    )

    assert len(embeds) == 1
    field_names = [field.name for field in embeds[0].fields]
    assert any("Team ?? (62.3%)" == name for name in field_names)
    assert any("Team ?? (37.7%)" == name for name in field_names)
