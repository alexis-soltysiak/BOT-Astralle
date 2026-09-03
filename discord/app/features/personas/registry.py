from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_PROFILES = Path(__file__).parent / "profiles"
_AVATARS = Path(__file__).parent / "avatars"


@dataclass(frozen=True)
class Persona:
    """Un personnage jouable par le bot.

    Ajouter un personnage = deposer un .md dans profiles/, une image dans
    avatars/, et une entree dans PERSONAS. Rien d'autre a toucher.
    """

    key: str
    command: str
    display_name: str
    description: str
    profile: str
    avatar: str | None = None

    def load_prompt(self) -> str:
        return (_PROFILES / self.profile).read_text(encoding="utf-8").strip()

    def load_avatar(self) -> bytes | None:
        if not self.avatar:
            return None
        path = _AVATARS / self.avatar
        return path.read_bytes() if path.is_file() else None


PERSONAS: tuple[Persona, ...] = (
    Persona(
        key="lisnard",
        command="lisnard",
        display_name="David Lisnard",
        description="David Lisnard donne son avis sur la conversation",
        profile="lisnard.md",
        avatar="lisnard.jpg",
    ),
    Persona(
        key="melenchon",
        command="melenchon",
        display_name="Jean-Luc Mélenchon",
        description="Jean-Luc Mélenchon donne son avis sur la conversation",
        profile="melenchon.md",
        avatar="melenchon.png",
    ),
    Persona(
        key="tondelier",
        command="tondelier",
        display_name="Marine Tondelier",
        description="Marine Tondelier donne son avis sur la conversation",
        profile="tondelier.md",
        avatar="tondelier.jpg",
    ),
    Persona(
        key="lepen",
        command="lepen",
        display_name="Marine Le Pen",
        description="Marine Le Pen donne son avis sur la conversation",
        profile="lepen.md",
        avatar="lepen.jpg",
    ),
    Persona(
        key="knafo",
        command="knafo",
        display_name="Sarah Knafo",
        description="Sarah Knafo donne son avis sur la conversation",
        profile="knafo.md",
        avatar="knafo.jpg",
    ),
    Persona(
        key="panot",
        command="panot",
        display_name="Mathilde Panot",
        description="Mathilde Panot donne son avis sur la conversation",
        profile="panot.md",
        avatar="panot.jpg",
    ),
    Persona(
        key="trump",
        command="trump",
        display_name="Donald Trump",
        description="Donald Trump donne son avis sur la conversation",
        profile="trump.md",
        avatar="trump.jpg",
    ),
    Persona(
        key="poutine",
        command="poutine",
        display_name="Vladimir Poutine",
        description="Vladimir Poutine donne son avis sur la conversation",
        profile="poutine.md",
        avatar="poutine.jpg",
    ),
)
