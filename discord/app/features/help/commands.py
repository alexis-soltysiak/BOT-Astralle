"""La commande /help : sommaire de tout ce que le bot sait faire.

Le bloc des personnalites est construit depuis le registre plutot qu'ecrit en
dur, pour qu'ajouter un personnage mette la page a jour toute seule.
"""

from __future__ import annotations

import discord
from discord import app_commands

from app.features.personas.registry import PERSONAS

_COLOR = discord.Color.from_str("#5865F2")

_LOL_COMMANDS = (
    ("/link", "Lier un compte Riot a une personne Discord"),
    ("/unlink", "Retirer un compte de la liste suivie"),
    ("/lastmatch", "Le detail de la derniere partie enregistree"),
    ("/last20", "Analyse de forme sur les 20 dernieres parties"),
)


def _persona_lines() -> str:
    return "\n".join(f"`/{p.command}` — {p.display_name}" for p in PERSONAS)


def build_help_embed(*, model: str, icon_url: str | None = None) -> discord.Embed:
    maximum = len(PERSONAS)

    embed = discord.Embed(
        title="Astralle",
        description=(
            "Un bot de suivi League of Legends, et un plateau de personnalites "
            "politiques qui commentent vos conversations."
        ),
        color=_COLOR,
    )
    if icon_url:
        embed.set_thumbnail(url=icon_url)

    embed.add_field(
        name="🎭  Faire réagir une personnalité",
        value=(
            f"{_persona_lines()}\n\n"
            "Chacune lit les 25 derniers messages du salon, comprend les liens "
            "partagés et les fils de réponses, puis rebondit sur le dernier "
            "message. Elle répond avec son nom et sa photo."
        ),
        inline=False,
    )

    embed.add_field(
        name="🗳️  Lancer un plateau",
        value=(
            f"`/sphere` `nombre:2-{maximum}`\n"
            "Plusieurs personnalités interviennent à la suite, espacées de 5 "
            "secondes. Le plateau est tiré au sort à chaque fois, et chacune "
            "voit ce que les précédentes ont dit — elles se répondent au lieu "
            "de se répéter."
        ),
        inline=False,
    )

    embed.add_field(
        name="📊  League of Legends",
        value="\n".join(f"`{name}` — {desc}" for name, desc in _LOL_COMMANDS),
        inline=False,
    )

    embed.add_field(
        name="💡  Bon à savoir",
        value=(
            "La recherche web ne s'active que si le salon parle d'actualité ou "
            "demande une vérification : le reste du temps elle est coupée, ce "
            "qui divise le coût par quatre.\n"
            "Les réponses sont des pastiches générés automatiquement, pas de "
            "vraies déclarations."
        ),
        inline=False,
    )

    embed.set_footer(text=f"Modèle {model}")
    return embed


def register(
    tree: app_commands.CommandTree,
    *,
    model: str,
    guild_id: int | None = None,
) -> None:
    scope: dict = {} if guild_id is None else {"guild": discord.Object(id=guild_id)}

    @tree.command(
        name="help",
        description="Affiche toutes les commandes du bot",
        **scope,
    )
    async def help_command(interaction: discord.Interaction) -> None:
        icon = interaction.client.user.display_avatar.url if interaction.client.user else None
        await interaction.response.send_message(
            embed=build_help_embed(model=model, icon_url=icon),
            ephemeral=True,
        )
