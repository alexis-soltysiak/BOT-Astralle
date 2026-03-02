from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import discord


def _slug(s: str) -> str:
    raw = (s or "").strip()
    norm = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    norm = norm.lower()
    norm = re.sub(r"[^a-z0-9]+", "_", norm).strip("_")
    norm = re.sub(r"_+", "_", norm)
    return norm


def _compact_slug(s: str) -> str:
    raw = (s or "").strip()
    norm = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    norm = norm.lower()
    return re.sub(r"[^a-z0-9]+", "", norm)


def _fmt_emoji(name: str, emoji_id: str) -> str:
    if not name or not emoji_id:
        return ""
    return f"<:{name}:{emoji_id}>"


@dataclass(frozen=True)
class EmojiRef:
    name: str
    emoji_id: str
    animated: bool = False

    def render(self) -> str:
        if not self.name or not self.emoji_id:
            return ""
        prefix = "a" if self.animated else ""
        return f"<{prefix}:{self.name}:{self.emoji_id}>"


class EmojiResolver:
    def __init__(self, client: discord.Client, application_id: int):
        self._client = client
        self._by_name: dict[str, EmojiRef] = {}
        self._fallback_by_name = self._load_fallback_emoji_map()

    def _load_fallback_emoji_map(self) -> dict[str, EmojiRef]:
        path = Path(__file__).resolve().parents[3] / "emoji_map.json"
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        items: list[dict] = []
        if isinstance(raw, dict):
            items = [item for item in raw.values() if isinstance(item, dict)]
        elif isinstance(raw, list):
            items = [item for item in raw if isinstance(item, dict)]
        else:
            return {}

        out: dict[str, EmojiRef] = {}
        for item in items:
            name = str(item.get("name") or item.get("discord_name") or "").strip()
            emoji_id = str(item.get("id") or item.get("discord_id") or "").strip()
            if not name or not emoji_id:
                continue
            out[name.lower()] = EmojiRef(name=name, emoji_id=emoji_id, animated=False)
        return out

    async def warmup(self) -> None:
        emojis = await self._client.fetch_application_emojis()
        self._by_name = {
            e.name.lower(): EmojiRef(name=e.name, emoji_id=str(e.id), animated=bool(getattr(e, "animated", False)))
            for e in emojis
            if e.name and e.id
        }

    def by_emoji_name(self, emoji_name: str) -> str:
        k = (emoji_name or "").lower().strip()
        ref = self._by_name.get(k)
        if ref is None:
            ref = self._fallback_by_name.get(k)
        return "" if ref is None else ref.render()

    def role(self, role: str) -> str:
        r = (role or "").upper().strip()
        if r == "TOP":
            return self.by_emoji_name("icone_top")
        if r == "JUNGLE":
            return self.by_emoji_name("icone_jungle")
        if r == "MID":
            return self.by_emoji_name("icone_mid")
        if r == "ADC":
            return self.by_emoji_name("icone_adc")
        if r == "SUPPORT":
            return self.by_emoji_name("icone_support")
        return ""

    def rank(self, tier: str | None) -> str:
        t = _slug(tier or "")
        if not t:
            return ""
        return self.by_emoji_name(f"rank_{t}")

    def champ_from_filename(self, champion_filename_stem: str) -> str:
        raw = champion_filename_stem or ""
        candidates: list[str] = []

        slug = _slug(raw)
        compact = _compact_slug(raw)
        if slug:
            candidates.append(slug)
        if compact and compact not in candidates:
            candidates.append(compact)

        # Riot display names and file stems are not always aligned with the emoji names.
        aliases = {
            "wukong": "monkeyking",
            "renataglasc": "renata",
            "drmundo": "drmundo",
            "nunuwillump": "nunu",
        }
        for candidate in list(candidates):
            alias = aliases.get(candidate)
            if alias and alias not in candidates:
                candidates.append(alias)

        for candidate in candidates:
            emoji = self.by_emoji_name(f"champ_{candidate}")
            if emoji:
                return emoji
        return ""

    def item(self, item_id: int | str | None) -> str:
        if item_id is None:
            return ""
        s = str(item_id).strip()
        if not s.isdigit():
            return ""
        return self.by_emoji_name(f"item_{s}")

    def rune_from_filename(self, rune_filename_stem: str) -> str:
        r = _slug(rune_filename_stem)
        if not r:
            return ""
        return self.by_emoji_name(f"rune_{r}")

    def rune_id(self, rune_id: int | str | None) -> str:
        if rune_id is None:
            return ""
        s = str(rune_id).strip()
        if not s.isdigit():
            return ""
        return self.by_emoji_name(f"rune_{s}")

    def spell_id(self, spell_id: int | str | None) -> str:
        if spell_id is None:
            return ""
        s = str(spell_id).strip()
        if not s.isdigit():
            return ""
        return self.by_emoji_name(f"spell_{s}")

    def scoring_category(self, category: str) -> str:
        c = (category or "").strip().lower()
        if c == "global":
            return self.by_emoji_name("scoring_global")
        if c == "vs_opponent":
            return self.by_emoji_name("scoring_lane")
        if c == "objectives":
            return self.by_emoji_name("scoring_objective")
        if c == "team":
            return self.by_emoji_name("scoring_team")
        if c == "role":
            return self.by_emoji_name("scoring_role")
        return ""
