from __future__ import annotations

import uuid
from types import SimpleNamespace

import httpx
import pytest

from app.features.live_games import service as live_games_service
from app.features.live_games.service import LiveGamesService


class FakeLiveGamesRepository:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def upsert_state(self, session, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)

    async def list_states(self, session):  # type: ignore[no-untyped-def]
        return []


class FakeTrackedPlayersRepository:
    def __init__(self, players) -> None:  # type: ignore[no-untyped-def]
        self.players = players

    async def get_all(self, session):  # type: ignore[no-untyped-def]
        return self.players


class FakeLeaderboardsRepository:
    def __init__(self, snapshots) -> None:  # type: ignore[no-untyped-def]
        self.snapshots = snapshots

    async def get_latest_snapshots(self, session):  # type: ignore[no-untyped-def]
        return self.snapshots


def _http_404() -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.test/live")
    response = httpx.Response(404, request=request)
    return httpx.HTTPStatusError("not found", request=request, response=response)


@pytest.mark.asyncio
async def test_refresh_marks_player_live_from_summoner_id_resolved_from_puuid(monkeypatch) -> None:
    player = SimpleNamespace(
        id=uuid.uuid4(),
        active=True,
        puuid="tracked-puuid",
        platform="euw1",
    )
    repo = FakeLiveGamesRepository()
    players_repo = FakeTrackedPlayersRepository([player])

    class FakeRiotClient:
        instances: list["FakeRiotClient"] = []

        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.summoner_calls: list[tuple[str, str]] = []
            self.calls: list[tuple[str, str]] = []
            self.rank_calls: list[tuple[str, str]] = []
            self.closed = False
            self.__class__.instances.append(self)

        async def get_summoner_by_puuid(self, platform: str, puuid: str) -> dict:
            self.summoner_calls.append((platform, puuid))
            return {"id": "encrypted-summoner-id"}

        async def get_active_game(self, platform: str, player_id: str) -> dict:
            self.calls.append((platform, player_id))
            return {
                "gameId": 7758161630,
                "gameQueueConfigId": 420,
                "participants": [{"puuid": "tracked-puuid", "championId": 103}],
            }

        async def get_league_entries_by_puuid(self, platform: str, puuid: str) -> list[dict]:
            self.rank_calls.append((platform, puuid))
            return [
                {
                    "queueType": "RANKED_SOLO_5x5",
                    "tier": "GOLD",
                    "rank": "II",
                    "leaguePoints": 80,
                    "wins": 10,
                    "losses": 8,
                }
            ]

        async def aclose(self) -> None:
            self.closed = True

    monkeypatch.setattr(
        "app.features.live_games.service.get_settings",
        lambda: SimpleNamespace(riot_api_key="test-key"),
    )
    monkeypatch.setattr("app.features.live_games.service.RiotClient", FakeRiotClient)

    async def _champ_map() -> dict[int, dict[str, str]]:
        return {103: {"key": "Ahri", "name": "Ahri"}}

    monkeypatch.setattr("app.features.live_games.service._get_champion_name_map", _champ_map)

    service = LiveGamesService(repo, players_repo)
    result = await service.refresh(session=None)

    assert result == {"updated": 1, "skipped": 0, "errors": 0, "targets": 1}
    assert repo.calls == [
        {
            "tracked_player_id": player.id,
            "platform": "euw1",
            "status": "live",
            "game_id": "7758161630",
            "payload": {
                "gameId": 7758161630,
                "gameQueueConfigId": 420,
                "participants": [
                    {
                        "puuid": "tracked-puuid",
                        "championId": 103,
                        "championKey": "Ahri",
                        "championName": "Ahri",
                        "soloRankedState": {
                            "queue_type": "RANKED_SOLO_5x5",
                            "tier": "GOLD",
                            "division": "II",
                            "league_points": 80,
                            "wins": 10,
                            "losses": 8,
                        },
                        "flexRankedState": {
                            "queue_type": "RANKED_FLEX_SR",
                            "tier": None,
                            "division": None,
                            "league_points": None,
                            "wins": None,
                            "losses": None,
                        },
                        "rankedState": {
                            "queue_type": "RANKED_SOLO_5x5",
                            "tier": "GOLD",
                            "division": "II",
                            "league_points": 80,
                            "wins": 10,
                            "losses": 8,
                        },
                    }
                ],
            },
        }
    ]
    assert FakeRiotClient.instances[0].summoner_calls == [("euw1", "tracked-puuid")]
    assert FakeRiotClient.instances[0].calls == [("euw1", "encrypted-summoner-id")]
    assert FakeRiotClient.instances[0].rank_calls == [("euw1", "tracked-puuid")]
    assert FakeRiotClient.instances[0].closed is True


@pytest.mark.asyncio
async def test_refresh_marks_player_none_on_404(monkeypatch) -> None:
    player = SimpleNamespace(
        id=uuid.uuid4(),
        active=True,
        puuid="tracked-puuid",
        platform="euw1",
    )
    repo = FakeLiveGamesRepository()
    players_repo = FakeTrackedPlayersRepository([player])

    class FakeRiotClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        async def get_summoner_by_puuid(self, platform: str, puuid: str) -> dict:
            return {"id": "encrypted-summoner-id"}

        async def get_active_game(self, platform: str, player_id: str) -> dict:
            raise _http_404()

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        "app.features.live_games.service.get_settings",
        lambda: SimpleNamespace(riot_api_key="test-key"),
    )
    monkeypatch.setattr("app.features.live_games.service.RiotClient", FakeRiotClient)

    service = LiveGamesService(repo, players_repo)
    result = await service.refresh(session=None)

    assert result == {"updated": 1, "skipped": 0, "errors": 0, "targets": 1}
    assert repo.calls == [
        {
            "tracked_player_id": player.id,
            "platform": "euw1",
            "status": "none",
            "game_id": None,
            "payload": None,
        }
    ]


@pytest.mark.asyncio
async def test_list_includes_discord_name_and_rank_snapshots() -> None:
    player = SimpleNamespace(
        id=uuid.uuid4(),
        active=True,
        puuid="tracked-puuid",
        platform="euw1",
        discord_display_name="Alex",
        game_name="Astral",
        tag_line="EUW",
    )
    state = SimpleNamespace(
        tracked_player_id=player.id,
        status="live",
        game_id="12345",
        payload={"gameId": 12345},
        fetched_at="2026-03-01T12:00:00Z",
    )
    solo = SimpleNamespace(
        tracked_player_id=player.id,
        queue_type="RANKED_SOLO_5x5",
        tier="GOLD",
        division="II",
        league_points=74,
        wins=10,
        losses=8,
        fetched_at="2026-03-01T11:58:00Z",
    )
    flex = SimpleNamespace(
        tracked_player_id=player.id,
        queue_type="RANKED_FLEX_SR",
        tier="PLATINUM",
        division="IV",
        league_points=12,
        wins=5,
        losses=4,
        fetched_at="2026-03-01T11:58:00Z",
    )

    repo = FakeLiveGamesRepository()

    async def _list_states(session):  # type: ignore[no-untyped-def]
        return [state]

    repo.list_states = _list_states  # type: ignore[method-assign]
    players_repo = FakeTrackedPlayersRepository([player])
    leaderboards_repo = FakeLeaderboardsRepository([solo, flex])

    service = LiveGamesService(repo, players_repo, leaderboards_repo)
    result = await service.list(session=None, only_active=True)

    assert len(result) == 1
    row = result[0]
    assert row.puuid == "tracked-puuid"
    assert row.discord_display_name == "Alex"
    assert row.solo.tier == "GOLD"
    assert row.solo.division == "II"
    assert row.solo.league_points == 74
    assert row.flex.tier == "PLATINUM"
    assert row.flex.division == "IV"
    assert row.flex.league_points == 12


@pytest.mark.asyncio
async def test_champion_name_map_uses_local_fallback_when_remote_fetch_fails(monkeypatch) -> None:
    class FailingAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FailingAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            return None

        async def get(self, url: str) -> None:
            raise httpx.ConnectError("network down")

    monkeypatch.setattr("app.features.live_games.service.httpx.AsyncClient", FailingAsyncClient)
    monkeypatch.setattr("app.features.live_games.service._CHAMPION_CACHE", {})
    monkeypatch.setattr("app.features.live_games.service._CHAMPION_CACHE_EXPIRES_AT", None)

    mapping = await live_games_service._get_champion_name_map()

    assert mapping[103] == {"key": "Ahri", "name": "Ahri"}
    assert mapping[266] == {"key": "Aatrox", "name": "Aatrox"}
