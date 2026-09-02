from __future__ import annotations

import re

import discord
import structlog
from discord import app_commands

from app.features.lisnard.client import LisnardClient

_LOG = structlog.get_logger("lisnard")

_MAX_MESSAGE_CHARS = 400
_MAX_EMBED_CHARS = 600
_DISCORD_LIMIT = 2000
_LAST_MARKER = ">>> DERNIER MESSAGE, c'est a ca que tu reagis <<<"

_CUSTOM_EMOJI = re.compile(r"<a?:(\w+):\d+>")
_ROLE_MENTION = re.compile(r"<@&(\d+)>")
_CHANNEL_MENTION = re.compile(r"<#(\d+)>")


def _author_name(message: discord.Message) -> str:
    author = message.author
    if isinstance(author, discord.Member):
        return author.display_name
    return author.global_name or author.name


def _normalize(text: object, *, limit: int) -> str:
    value = " ".join(str(text or "").split())
    value = _CUSTOM_EMOJI.sub(r":\1:", value)
    value = _ROLE_MENTION.sub("@role", value)
    value = _CHANNEL_MENTION.sub("#salon", value)
    if len(value) > limit:
        value = value[:limit].rstrip() + "..."
    return value


def _embed_text(embed: discord.Embed) -> str:
    """Aplatit un embed Discord en texte lisible.

    Quand quelqu'un colle un lien Twitter/X, Bluesky, YouTube ou un article, le
    message lui-meme ne contient que l'URL : tout le contenu utile (auteur,
    texte du post, titre de l'article) vit dans l'embed genere par Discord.
    Sans ca, Lisnard ne voit qu'une URL nue et ne peut pas rebondir dessus.
    """
    parts: list[str] = []

    author = getattr(embed.author, "name", None)
    if author:
        parts.append(_normalize(author, limit=80))

    if embed.title:
        parts.append(_normalize(embed.title, limit=160))

    if embed.description:
        parts.append(_normalize(embed.description, limit=_MAX_EMBED_CHARS))

    for field in embed.fields[:4]:
        name = _normalize(getattr(field, "name", ""), limit=60)
        value = _normalize(getattr(field, "value", ""), limit=160)
        if name and value:
            parts.append(f"{name}: {value}")
        elif value:
            parts.append(value)

    footer = getattr(embed.footer, "text", None)
    if footer:
        parts.append(_normalize(footer, limit=60))

    if not parts and embed.url:
        parts.append(_normalize(embed.url, limit=120))

    return " | ".join(part for part in parts if part)


def _attachment_text(message: discord.Message) -> str:
    labels: list[str] = []
    for attachment in getattr(message, "attachments", [])[:3]:
        content_type = str(getattr(attachment, "content_type", "") or "")
        kind = "image" if content_type.startswith("image/") else "fichier"
        labels.append(f"[{kind} joint: {_normalize(attachment.filename, limit=40)}]")
    return " ".join(labels)


def reply_context(message: discord.Message) -> str:
    """Rend visible le message auquel celui-ci repond.

    Sur un salon qui debat, la moitie des messages sont des replies Discord.
    Sans ce lien, une phrase comme "ca revient au meme ?" n'a plus aucun sens
    et le modele repond a cote.
    """
    reference = getattr(message, "reference", None)
    resolved = getattr(reference, "resolved", None) if reference is not None else None
    if resolved is None or not hasattr(resolved, "author"):
        return ""

    quoted = _normalize(getattr(resolved, "clean_content", ""), limit=120)
    if not quoted:
        for embed in getattr(resolved, "embeds", [])[:1]:
            quoted = _normalize(_embed_text(embed), limit=120)
    if not quoted:
        return ""

    return f'(en reponse a {_author_name(resolved)} "{quoted}") '


def extract_message_text(message: discord.Message) -> str:
    """Texte du message, plus le contenu des embeds et des pieces jointes."""
    chunks: list[str] = []

    # clean_content resout deja les mentions utilisateur en noms lisibles
    body = _normalize(message.clean_content, limit=_MAX_MESSAGE_CHARS)
    if body:
        chunks.append(body)

    for embed in getattr(message, "embeds", [])[:2]:
        rendered = _embed_text(embed)
        if rendered:
            chunks.append(f"[contenu du lien -> {rendered}]")

    attachments = _attachment_text(message)
    if attachments:
        chunks.append(attachments)

    return " ".join(chunks).strip()


def build_transcript(messages: list[discord.Message]) -> str:
    """messages: du plus ancien au plus recent."""
    lines: list[str] = []
    for index, message in enumerate(messages):
        text = extract_message_text(message)
        if not text:
            continue
        is_last = index == len(messages) - 1
        prefix = f"{_LAST_MARKER}\n" if is_last else ""
        head = f"{_author_name(message)} {reply_context(message)}".rstrip()
        lines.append(f"{prefix}{head}: {text}")
    return "\n".join(lines)


async def _collect_history(
    channel: discord.abc.Messageable,
    *,
    limit: int,
    exclude_id: int | None,
) -> list[discord.Message]:
    collected: list[discord.Message] = []
    async for message in channel.history(limit=limit + 5):
        if exclude_id is not None and message.id == exclude_id:
            continue
        if not extract_message_text(message):
            continue
        collected.append(message)
        if len(collected) >= limit:
            break
    collected.reverse()
    return collected


_NAME_PREFIX = re.compile(r"^\s*(david\s+)?lisnard\s*[:\-–]\s*", re.IGNORECASE)


def clean_reply(text: str) -> str:
    """Retire les artefacts de jeu de role qui trahiraient le bot.

    Les modeles ont tendance a prefixer par le nom du personnage ou a encadrer
    la replique de guillemets, comme dans un script. Un vrai message Discord
    n'a ni l'un ni l'autre.
    """
    cleaned = text.strip()
    cleaned = _NAME_PREFIX.sub("", cleaned)

    for opening, closing in (('"', '"'), ("«", "»"), ("“", "”"), ("'", "'")):
        if len(cleaned) > 1 and cleaned.startswith(opening) and cleaned.endswith(closing):
            cleaned = cleaned[len(opening) : -len(closing)].strip()

    # pas de ligne vide au milieu : sur Discord ca fait tout de suite redige
    cleaned = "\n".join(line for line in cleaned.splitlines() if line.strip())
    return cleaned.strip()


def _truncate_for_discord(text: str) -> str:
    if len(text) <= _DISCORD_LIMIT:
        return text
    return text[: _DISCORD_LIMIT - 1].rstrip() + "…"


def register(
    tree: app_commands.CommandTree,
    lisnard: LisnardClient,
    *,
    history_limit: int = 25,
) -> None:
    """Enregistre /lisnard en GLOBAL, volontairement.

    Les autres commandes sont scopees sur DISCORD_GUILD_ID parce qu'elles
    dependent du suivi LoL d'un serveur precis. /lisnard ne depend de rien :
    elle doit marcher sur n'importe quel serveur ou le bot est invite. La
    contrepartie est le delai de propagation Discord, qui peut aller jusqu'a
    une heure apres un premier deploiement.
    """

    @tree.command(name="lisnard", description="David Lisnard donne son avis sur la conversation")
    async def lisnard_command(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        if not lisnard.enabled:
            await interaction.followup.send(
                "Lisnard est desactive (LISNARD_ENABLED ou LLM_API_KEY manquant).",
                ephemeral=True,
            )
            return

        channel = interaction.channel
        if channel is None or not isinstance(channel, discord.abc.Messageable):
            await interaction.followup.send("Salon illisible.", ephemeral=True)
            return

        try:
            messages = await _collect_history(
                channel,
                limit=history_limit,
                exclude_id=None,
            )
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

        raw = await lisnard.generate(transcript)
        reply = clean_reply(raw) if raw else ""
        if not reply:
            await interaction.followup.send(
                "Pas de reponse du modele, reessaie.",
                ephemeral=True,
            )
            return

        try:
            await channel.send(
                _truncate_for_discord(reply),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "Il me manque la permission Send Messages sur ce salon.",
                ephemeral=True,
            )
            return

        _LOG.info(
            "lisnard_replied",
            guild_id=None if interaction.guild is None else interaction.guild.id,
            channel_id=getattr(channel, "id", None),
            messages_read=len(messages),
        )
        await interaction.followup.send("Envoye.", ephemeral=True)
