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


def _short_label(name: str, max_len: int = 24) -> str:
    value = " ".join(str(name or "").split())
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rstrip() + "…"


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
        analysis_embed: discord.Embed | None = None,
    ):
        super().__init__(timeout=None)
        self._base_embed = base_embed.copy()
        self._score_payload = score_payload
        self._player_name = player_name
        self._author_name = author_name
        self._author_icon_url = author_icon_url
        self._embed_color = embed_color
        self._resolver = resolver
        self._analysis_embed = analysis_embed.copy() if analysis_embed is not None else None
        role = str(score_payload.get("role") or "UNKNOWN")
        self.btn_role.label = _role_label(role)
        self.btn_advice.disabled = analysis_embed is None

    async def _edit(self, interaction: discord.Interaction, cat: str | None) -> None:
        if cat is None:
            await interaction.response.edit_message(embed=self._base_embed, view=self)
            return
        if cat == "analysis":
            if self._analysis_embed is None:
                await interaction.response.edit_message(embed=self._base_embed, view=self)
                return
            await interaction.response.edit_message(embed=self._analysis_embed, view=self)
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

    @discord.ui.button(
        label="Conseils",
        style=discord.ButtonStyle.success,
        custom_id="score_advice",
        row=0,
    )
    async def btn_advice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._edit(interaction, "analysis")

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


class MatchTrackedPlayersView(discord.ui.View):
    def __init__(self, *, player_cards: list[dict]) -> None:
        super().__init__(timeout=None)
        self._cards = {str(card.get("puuid") or ""): card for card in player_cards if str(card.get("puuid") or "")}
        self._order = [str(card.get("puuid") or "") for card in player_cards if str(card.get("puuid") or "")]
        self._mode = "stats"
        self._current_puuid = self._order[0] if self._order else None
        self._stats_buttons: list[discord.ui.Button] = []
        self._advice_buttons: list[discord.ui.Button] = []
        self._build_buttons()
        self._sync_button_state()

    def _build_buttons(self) -> None:
        for index, puuid in enumerate(self._order):
            card = self._cards.get(puuid) or {}
            label = _short_label(str(card.get("player_name") or "Joueur"))
            stats_button = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.secondary,
                row=0 if index < 5 else 1,
                custom_id=f"match_stats_{index}",
            )
            advice_button = discord.ui.Button(
                label=f"Conseil {label}",
                style=discord.ButtonStyle.secondary,
                row=2 if index < 5 else 3,
                custom_id=f"match_advice_{index}",
                disabled=card.get("analysis_embed") is None,
            )

            async def _stats_callback(interaction: discord.Interaction, target_puuid: str = puuid) -> None:
                await self._switch(interaction, target_puuid, "stats")

            async def _advice_callback(interaction: discord.Interaction, target_puuid: str = puuid) -> None:
                await self._switch(interaction, target_puuid, "advice")

            stats_button.callback = _stats_callback
            advice_button.callback = _advice_callback
            self._stats_buttons.append(stats_button)
            self._advice_buttons.append(advice_button)
            self.add_item(stats_button)
            self.add_item(advice_button)

    def _sync_button_state(self) -> None:
        for idx, puuid in enumerate(self._order):
            is_current_stats = self._current_puuid == puuid and self._mode == "stats"
            is_current_advice = self._current_puuid == puuid and self._mode == "advice"
            self._stats_buttons[idx].style = (
                discord.ButtonStyle.primary if is_current_stats else discord.ButtonStyle.secondary
            )
            self._advice_buttons[idx].style = (
                discord.ButtonStyle.success if is_current_advice else discord.ButtonStyle.secondary
            )

    def _current_embed(self) -> discord.Embed | None:
        if self._current_puuid is None:
            return None
        card = self._cards.get(self._current_puuid) or {}
        if self._mode == "advice":
            advice = card.get("analysis_embed")
            if isinstance(advice, discord.Embed):
                return advice
        base = card.get("base_embed")
        if isinstance(base, discord.Embed):
            return base
        return None

    async def _switch(self, interaction: discord.Interaction, puuid: str, mode: str) -> None:
        self._current_puuid = puuid
        self._mode = "advice" if mode == "advice" else "stats"
        current = self._cards.get(puuid) or {}
        if self._mode == "advice" and current.get("analysis_embed") is None:
            self._mode = "stats"
        self._sync_button_state()
        embed = self._current_embed()
        if embed is None:
            return await interaction.response.defer()
        await interaction.response.edit_message(embed=embed, view=self)
