"""Publication d'un message sous l'identite visuelle d'un personnage.

Discord ne permet pas a un bot de changer de nom et d'avatar par message. Les
webhooks, si : chaque message envoye via un webhook porte le nom et l'image du
webhook. On cree donc un webhook par personnage et par salon, ce qui fait
apparaitre Lisnard et Melenchon comme deux interlocuteurs distincts alors qu'il
s'agit du meme bot.

Sans la permission Manage Webhooks, on retombe sur un envoi classique prefixe
du nom : moins joli, mais la commande continue de fonctionner.
"""

from __future__ import annotations

import discord
import structlog

from app.features.personas.registry import Persona

_LOG = structlog.get_logger("personas")


class PersonaWebhooks:
    def __init__(self) -> None:
        # (channel_id, persona.key) -> webhook
        self._cache: dict[tuple[int, str], discord.Webhook] = {}
        self._avatars: dict[str, bytes | None] = {}

    def _avatar(self, persona: Persona) -> bytes | None:
        if persona.key not in self._avatars:
            try:
                self._avatars[persona.key] = persona.load_avatar()
            except OSError as e:
                _LOG.warning("persona_avatar_unreadable", persona=persona.key, error=str(e))
                self._avatars[persona.key] = None
        return self._avatars[persona.key]

    async def _webhook_for(
        self,
        channel: discord.TextChannel,
        persona: Persona,
    ) -> discord.Webhook | None:
        key = (channel.id, persona.key)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        try:
            existing = await channel.webhooks()
        except (discord.Forbidden, discord.HTTPException) as e:
            _LOG.info("persona_webhook_list_failed", persona=persona.key, error=str(e))
            return None

        webhook = discord.utils.get(existing, name=persona.display_name)
        if webhook is None:
            try:
                webhook = await channel.create_webhook(
                    name=persona.display_name,
                    avatar=self._avatar(persona),
                    reason="Identite visuelle du personnage",
                )
            except (discord.Forbidden, discord.HTTPException) as e:
                _LOG.info("persona_webhook_create_failed", persona=persona.key, error=str(e))
                return None

        self._cache[key] = webhook
        return webhook

    async def send(
        self,
        channel: discord.abc.Messageable,
        persona: Persona,
        content: str,
    ) -> bool:
        """Poste le message. Renvoie True si l'identite visuelle a pu etre utilisee."""
        # dans un fil, le webhook appartient au salon parent et on cible le fil
        thread: discord.Thread | None = channel if isinstance(channel, discord.Thread) else None
        parent = channel.parent if isinstance(channel, discord.Thread) else channel

        if isinstance(parent, discord.TextChannel):
            target = parent
            webhook = await self._webhook_for(target, persona)
            if webhook is not None:
                kwargs: dict = {"allowed_mentions": discord.AllowedMentions.none()}
                if thread is not None:
                    kwargs["thread"] = thread
                try:
                    await webhook.send(content, **kwargs)
                    return True
                except discord.NotFound:
                    # webhook supprime entre-temps : on purge et on repartira propre
                    self._cache.pop((target.id, persona.key), None)
                except discord.HTTPException as e:
                    _LOG.warning("persona_webhook_send_failed", persona=persona.key, error=str(e))

        await channel.send(
            f"**{persona.display_name}** — {content}",
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return False
