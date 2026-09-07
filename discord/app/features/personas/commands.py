from __future__ import annotations

import asyncio
import random

import discord
import structlog
from discord import app_commands

from app.features.personas.client import (
    PersonaClient,
    sanitize_directive,
    with_prior_replies,
)
from app.features.personas.registry import PERSONAS, Persona
from app.features.personas.transcript import (
    build_transcript,
    clean_reply,
    collect_history,
    needs_web_search,
    truncate_for_discord,
)
from app.features.personas.webhooks import PersonaWebhooks

_LOG = structlog.get_logger("personas")

# Delai entre deux prises de parole du plateau, pour que ca se lise.
_SPHERE_DELAY_SECONDS = 5.0

# Le plateau lit moins loin qu'une commande solo : le contexte est multiplie par
# le nombre d'intervenants, donc chaque message economise compte.
_SPHERE_HISTORY_LIMIT = 12


def _register_one(
    tree: app_commands.CommandTree,
    client: PersonaClient,
    webhooks: PersonaWebhooks,
    persona: Persona,
    *,
    history_limit: int,
    guild_id: int | None,
) -> None:
    """Une fonction par personnage : chaque commande capture SA persona.

    Le scope passe par le parametre guild de tree.command, et surtout PAS par un
    decorateur @app_commands.guilds place au-dessus : tree.command enregistre la
    commande des qu'il s'applique, donc un decorateur pose au-dessus arrive trop
    tard et la commande part en global.
    """
    scope: dict = {} if guild_id is None else {"guild": discord.Object(id=guild_id)}

    @tree.command(name=persona.command, description=persona.description, **scope)
    @app_commands.describe(
        consigne="Optionnel : oriente la reponse, ex. \"reponds a JH sur le voile\""
    )
    async def _command(interaction: discord.Interaction, consigne: str | None = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        if not client.enabled:
            await interaction.followup.send(
                "Les personnages sont desactives (PERSONA_ENABLED ou LLM_API_KEY manquant).",
                ephemeral=True,
            )
            return

        channel = interaction.channel
        if channel is None or not isinstance(channel, discord.abc.Messageable):
            await interaction.followup.send("Salon illisible.", ephemeral=True)
            return

        try:
            messages = await collect_history(channel, limit=history_limit, exclude_id=None)
        except discord.Forbidden:
            await interaction.followup.send(
                "Il me manque la permission Read Message History sur ce salon.",
                ephemeral=True,
            )
            return

        if not messages:
            await interaction.followup.send(
                "Aucun message lisible ici. Si le salon n'est pas vide, active le "
                "Message Content Intent dans le Discord Developer Portal.",
                ephemeral=True,
            )
            return

        transcript = build_transcript(messages)
        if not transcript.strip():
            await interaction.followup.send(
                "Aucun contenu texte lisible dans les derniers messages.",
                ephemeral=True,
            )
            return

        directive = sanitize_directive(consigne)

        # L'outil web_search coute plus cher que la fiche du personnage : on ne
        # l'attache que si le salon, ou la consigne, parle d'actualite.
        search = needs_web_search(transcript, directive)
        raw = await client.generate(
            persona, transcript, web_search=search, directive=directive
        )
        reply = clean_reply(raw, persona.display_name) if raw else ""
        if not reply:
            await interaction.followup.send("Pas de reponse du modele, reessaie.", ephemeral=True)
            return

        try:
            impersonated = await webhooks.send(channel, persona, truncate_for_discord(reply))
        except discord.Forbidden:
            await interaction.followup.send(
                "Il me manque la permission Send Messages sur ce salon.",
                ephemeral=True,
            )
            return

        _LOG.info(
            "persona_replied",
            persona=persona.key,
            guild_id=None if interaction.guild is None else interaction.guild.id,
            channel_id=getattr(channel, "id", None),
            messages_read=len(messages),
            web_search=search,
            guided=bool(directive),
            impersonated=impersonated,
        )
        await interaction.followup.send(
            "Envoye."
            if impersonated
            else (
                "Envoye, mais sans l'avatar : il me manque la permission Manage Webhooks "
                "sur ce salon."
            ),
            ephemeral=True,
        )


def pick_panel(count: int, personas: tuple[Persona, ...] = PERSONAS) -> list[Persona]:
    """Tire au sort `count` personnages distincts, dans un ordre aleatoire."""
    return random.sample(list(personas), k=max(0, min(count, len(personas))))


def _register_sphere(
    tree: app_commands.CommandTree,
    client: PersonaClient,
    webhooks: PersonaWebhooks,
    *,
    guild_id: int | None,
) -> None:
    scope: dict = {} if guild_id is None else {"guild": discord.Object(id=guild_id)}
    maximum = len(PERSONAS)

    @tree.command(
        name="sphere",
        description="Fait reagir plusieurs personnalites politiques a la suite",
        **scope,
    )
    @app_commands.describe(
        nombre=f"Combien de personnalites repondent (2 a {maximum})",
        consigne='Optionnel : oriente le plateau, ex. "debattez du vote utile"',
    )
    async def sphere(
        interaction: discord.Interaction,
        nombre: int = 3,
        consigne: str | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        if not client.enabled:
            await interaction.followup.send(
                "Les personnages sont desactives (PERSONA_ENABLED ou LLM_API_KEY manquant).",
                ephemeral=True,
            )
            return

        if not 2 <= nombre <= maximum:
            await interaction.followup.send(
                f"Choisis un nombre entre 2 et {maximum}.", ephemeral=True
            )
            return

        channel = interaction.channel
        if channel is None or not isinstance(channel, discord.abc.Messageable):
            await interaction.followup.send("Salon illisible.", ephemeral=True)
            return

        try:
            messages = await collect_history(
                channel, limit=_SPHERE_HISTORY_LIMIT, exclude_id=None
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "Il me manque la permission Read Message History sur ce salon.",
                ephemeral=True,
            )
            return

        transcript = build_transcript(messages)
        if not transcript.strip():
            await interaction.followup.send(
                "Aucun contenu texte lisible dans les derniers messages.", ephemeral=True
            )
            return

        directive = sanitize_directive(consigne)
        panel = pick_panel(nombre)
        await interaction.followup.send(
            f"Le plateau arrive : {', '.join(p.display_name for p in panel)}.",
            ephemeral=True,
        )

        said: list[tuple[str, str]] = []
        for index, persona in enumerate(panel):
            if index:
                await asyncio.sleep(_SPHERE_DELAY_SECONDS)

            # Pas de recherche web ici : la definition de l'outil coute plus de
            # tokens que la fiche du personnage, et le plateau reagit au salon,
            # pas a l'actualite.
            raw = await client.generate(
                persona,
                with_prior_replies(transcript, said),
                web_search=False,
                directive=directive,
            )
            reply = clean_reply(raw, persona.display_name) if raw else ""
            if not reply:
                continue

            try:
                await webhooks.send(channel, persona, truncate_for_discord(reply))
            except discord.Forbidden:
                await interaction.followup.send(
                    "Il me manque la permission Send Messages sur ce salon.", ephemeral=True
                )
                return
            said.append((persona.display_name, reply))

        _LOG.info(
            "sphere_replied",
            guild_id=None if interaction.guild is None else interaction.guild.id,
            channel_id=getattr(channel, "id", None),
            asked=nombre,
            answered=len(said),
            guided=bool(directive),
            panel=[p.key for p in panel],
        )


def register(
    tree: app_commands.CommandTree,
    client: PersonaClient,
    *,
    history_limit: int = 25,
    guild_id: int | None = None,
) -> None:
    """Declare une slash command par personnage, plus la commande de groupe."""
    webhooks = PersonaWebhooks()
    for persona in PERSONAS:
        _register_one(
            tree,
            client,
            webhooks,
            persona,
            history_limit=history_limit,
            guild_id=guild_id,
        )
    _register_sphere(tree, client, webhooks, guild_id=guild_id)
