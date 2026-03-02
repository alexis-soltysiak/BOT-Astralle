from __future__ import annotations

import discord
import httpx
from discord import app_commands

from app.core.backend_client import BackendClient
from app.features.pinned.leaderboard import refresh_leaderboard_message


def _target_member(interaction: discord.Interaction, member: discord.Member | None) -> discord.abc.User:
    return member if member is not None else interaction.user


def _display_name(user: discord.abc.User) -> str:
    if isinstance(user, discord.Member):
        return user.display_name
    return user.global_name or user.name


async def _refresh_leaderboard_after_roster_change(
    interaction: discord.Interaction,
    backend: BackendClient,
) -> None:
    guild = interaction.guild
    if guild is None:
        return

    bindings = await backend.list_discord_bindings(guild_id=guild.id)
    binding = next((b for b in bindings if str(b.get("binding_key") or "") == "LEADERBOARD_MESSAGE"), None)
    if binding is None:
        return

    await refresh_leaderboard_message(
        bot=interaction.client,
        backend=backend,
        guild_id=guild.id,
        binding=binding,
    )


def register(
    tree: app_commands.CommandTree,
    backend: BackendClient,
    guild_id: int | None = None,
) -> None:
    guild_decorator = (
        app_commands.guilds(discord.Object(id=guild_id))
        if guild_id is not None
        else (lambda command: command)
    )

    @guild_decorator
    @tree.command(name="link", description="Lie un compte LoL a une personne Discord")
    @app_commands.describe(
        game_name="Pseudo Riot sans le #",
        tag_line="Tag Riot apres le #",
        member="Personne Discord a lier (optionnel)",
    )
    async def link(
        interaction: discord.Interaction,
        game_name: str,
        tag_line: str,
        member: discord.Member | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=False)
        target = _target_member(interaction, member)

        try:
            created = await backend.create_tracked_player(
                {
                    "discord_user_id": str(target.id),
                    "discord_display_name": _display_name(target),
                    "game_name": game_name,
                    "tag_line": tag_line,
                    "region": "europe",
                    "platform": "euw1",
                    "active": True,
                }
            )
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:400]
            await interaction.followup.send(
                f"Echec du link pour `{game_name}#{tag_line}`: {exc.response.status_code} {detail}",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"Echec du link pour `{game_name}#{tag_line}`: {exc}",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            (
                f"Compte lie: `{created.get('game_name')}#{created.get('tag_line')}` -> "
                f"<@{created.get('discord_user_id')}>"
            ),
            ephemeral=True,
        )
        try:
            await _refresh_leaderboard_after_roster_change(interaction, backend)
        except Exception:
            pass

    @guild_decorator
    @tree.command(name="unlink", description="Retire un compte LoL de la liste trackee")
    @app_commands.describe(
        game_name="Pseudo Riot sans le #",
        tag_line="Tag Riot apres le #",
    )
    async def unlink(
        interaction: discord.Interaction,
        game_name: str,
        tag_line: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=False)
        try:
            tracked = await backend.list_tracked_players()
        except Exception as exc:
            await interaction.followup.send(f"Impossible de lire les comptes trackes: {exc}", ephemeral=True)
            return

        match = next(
            (
                p
                for p in tracked
                if str(p.get("game_name") or "").casefold() == game_name.casefold()
                and str(p.get("tag_line") or "").casefold() == tag_line.casefold()
            ),
            None,
        )
        if match is None:
            await interaction.followup.send(f"Compte introuvable: `{game_name}#{tag_line}`", ephemeral=True)
            return

        player_id = str(match.get("id") or "")
        if not player_id:
            await interaction.followup.send("Compte invalide: id manquant.", ephemeral=True)
            return

        try:
            await backend.delete_tracked_player(player_id)
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:400]
            await interaction.followup.send(
                f"Echec du unlink pour `{game_name}#{tag_line}`: {exc.response.status_code} {detail}",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"Echec du unlink pour `{game_name}#{tag_line}`: {exc}",
                ephemeral=True,
            )
            return

        await interaction.followup.send(f"Compte retire: `{game_name}#{tag_line}`", ephemeral=True)
        try:
            await _refresh_leaderboard_after_roster_change(interaction, backend)
        except Exception:
            pass
