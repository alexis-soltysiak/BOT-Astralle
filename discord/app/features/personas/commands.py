from __future__ import annotations

import discord
import structlog
from discord import app_commands

from app.features.personas.client import PersonaClient
from app.features.personas.registry import PERSONAS, Persona
from app.features.personas.transcript import (
    build_transcript,
    clean_reply,
    collect_history,
    truncate_for_discord,
)
from app.features.personas.webhooks import PersonaWebhooks

_LOG = structlog.get_logger("personas")


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
    async def _command(interaction: discord.Interaction) -> None:
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

        raw = await client.generate(persona, transcript)
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


def register(
    tree: app_commands.CommandTree,
    client: PersonaClient,
    *,
    history_limit: int = 25,
    guild_id: int | None = None,
) -> None:
    """Declare une slash command par personnage du registre."""
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
