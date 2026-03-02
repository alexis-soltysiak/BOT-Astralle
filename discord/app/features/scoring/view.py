from __future__ import annotations

import discord

from app.core.emoji_resolver import EmojiResolver
from app.features.scoring.breakdown import build_category_breakdown_embed


def _role_label(role: str) -> str:
    r = (role or "").upper().strip()
    if r == "TOP":
        return "Top"
    if r == "JUNGLE":
        return "Jungle"
    if r == "MID":
        return "Mid"
    if r == "ADC":
        return "ADC"
    if r == "SUPPORT":
        return "Support"
    return "Role"


class MatchScoreBreakdownView(discord.ui.View):
    def __init__(
        self,
        *,
        base_embed: discord.Embed,
        score_payload: dict,
        player_name: str,
        author_name: str | None = None,
        author_icon_url: str | None = None,
        embed_color: discord.Color | None = None,
        resolver: EmojiResolver | None = None,
    ):
        super().__init__(timeout=None)
        self._base_embed = base_embed.copy()
        self._score_payload = score_payload
        self._player_name = player_name
        self._author_name = author_name
        self._author_icon_url = author_icon_url
        self._embed_color = embed_color
        self._resolver = resolver
        role = str(score_payload.get("role") or "UNKNOWN")
        self.btn_role.label = _role_label(role)

    async def _edit(self, interaction: discord.Interaction, cat: str | None) -> None:
        if cat is None:
            await interaction.response.edit_message(embed=self._base_embed, view=self)
            return

        embed = build_category_breakdown_embed(
            cat=cat,
            score_payload=self._score_payload,
            player_name=self._player_name,
            author_name=self._author_name,
            author_icon_url=self._author_icon_url,
            embed_color=self._embed_color,
            resolver=self._resolver,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label="Revenir a l'embed de base",
        style=discord.ButtonStyle.primary,
        custom_id="score_back",
        row=0,
    )
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._edit(interaction, None)

    @discord.ui.button(label="Global", style=discord.ButtonStyle.secondary, custom_id="score_global", row=1)
    async def btn_global(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._edit(interaction, "global")

    @discord.ui.button(label="vs Opponent", style=discord.ButtonStyle.secondary, custom_id="score_vs", row=1)
    async def btn_vs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._edit(interaction, "vs_opponent")

    @discord.ui.button(label="Objectives", style=discord.ButtonStyle.secondary, custom_id="score_obj", row=1)
    async def btn_obj(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._edit(interaction, "objectives")

    @discord.ui.button(label="Team", style=discord.ButtonStyle.secondary, custom_id="score_team", row=1)
    async def btn_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._edit(interaction, "team")

    @discord.ui.button(label="Role", style=discord.ButtonStyle.secondary, custom_id="score_role", row=1)
    async def btn_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._edit(interaction, "role")
