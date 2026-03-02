from __future__ import annotations

from urllib.parse import quote

import httpx


class RiotClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=20.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, url: str) -> dict | list:
        res = await self._client.get(url, headers={"X-Riot-Token": self._api_key})
        res.raise_for_status()
        return res.json()

    async def get_account_by_riot_id(self, region: str, game_name: str, tag_line: str) -> dict:
        gn = quote(game_name, safe="")
        tl = quote(tag_line, safe="")
        url = f"https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{gn}/{tl}"
        data = await self._get(url)
        return data  # type: ignore[return-value]

    async def get_league_entries_by_puuid(self, platform: str, puuid: str) -> list[dict]:
        url = f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
        data = await self._get(url)
        return data  # type: ignore[return-value]

    async def get_summoner_by_puuid(self, platform: str, puuid: str) -> dict:
        url = f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
        data = await self._get(url)
        return data  # type: ignore[return-value]

    async def get_active_game(self, platform: str, player_id: str) -> dict:
        url = f"https://{platform}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{player_id}"
        data = await self._get(url)
        return data  # type: ignore[return-value]

    async def get_match_ids_by_puuid(self, region: str, puuid: str, start: int, count: int) -> list[str]:
        url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}"
        data = await self._get(url)
        return [str(x) for x in data]  # type: ignore[arg-type]

    async def get_match(self, region: str, riot_match_id: str) -> dict:
        url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{riot_match_id}"
        data = await self._get(url)
        return data  # type: ignore[return-value]
