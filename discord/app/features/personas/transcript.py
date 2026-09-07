"""Extraction du contexte d'un salon Discord et nettoyage des reponses."""

from __future__ import annotations

import re
import unicodedata

import discord

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
    Sans ca, le personnage ne voit qu'une URL nue et ne peut pas rebondir dessus.
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


async def collect_history(
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


def _name_prefix_pattern(display_name: str) -> re.Pattern[str]:
    """Reconnait "Jean-Luc Melenchon :" aussi bien que "Melenchon -"."""
    parts = [re.escape(part) for part in display_name.split() if part]
    if not parts:
        return re.compile(r"(?!)")
    full = r"\s+".join(parts)
    surname = parts[-1]
    return re.compile(rf"^\s*(?:{full}|{surname})\s*[:\-–—]\s*", re.IGNORECASE)


def clean_reply(text: str, display_name: str = "") -> str:
    """Retire les artefacts de jeu de role qui trahiraient le bot.

    Les modeles ont tendance a prefixer par le nom du personnage ou a encadrer
    la replique de guillemets, comme dans un script. Un vrai message Discord
    n'a ni l'un ni l'autre.
    """
    cleaned = text.strip()
    if display_name:
        cleaned = _name_prefix_pattern(display_name).sub("", cleaned)

    for opening, closing in (('"', '"'), ("«", "»"), ("“", "”"), ("'", "'")):
        if len(cleaned) > 1 and cleaned.startswith(opening) and cleaned.endswith(closing):
            cleaned = cleaned[len(opening) : -len(closing)].strip()

    # pas de ligne vide au milieu : sur Discord ca fait tout de suite redige
    cleaned = "\n".join(line for line in cleaned.splitlines() if line.strip())
    return cleaned.strip()


def truncate_for_discord(text: str) -> str:
    if len(text) <= _DISCORD_LIMIT:
        return text
    return text[: _DISCORD_LIMIT - 1].rstrip() + "…"


# --- Faut-il payer la recherche web sur cet appel ? -------------------------
#
# La seule definition de l'outil web_search coute 4436 tokens d'entree, soit
# plus que la fiche d'un personnage : elle multiplie par ~4 le cout d'un appel,
# y compris quand aucune recherche n'a lieu. Mesure faite sur cinq scenarios,
# le modele ne cherche que sur les questions d'actualite verifiable. On ne lui
# attache donc l'outil que quand le salon a l'air d'en avoir besoin.

_URL_RE = re.compile(r"https?://", re.IGNORECASE)

# Marqueurs de fraicheur : on parle de quelque chose de date ou de recent.
_FRESHNESS_RE = re.compile(
    r"\b("
    r"aujourd\s*hui|hier|avant-?hier|ce matin|ce soir|cette semaine|ce mois|"
    r"en ce moment|actuellement|recemment|recent[e]?s?|"
    r"actu|actualites?|news|infos?|"
    r"sondages?|elections?|resultats?|scrutin|"
    r"annonces?|a annonce|vient de|a declare|a dit que|"
    r"demission|remaniement|proces|jugement|verdict|condamn\w*|"
    r"20(?:2[4-9]|3\d)"
    r")\b"
)

# Marqueurs de verification : on demande si un fait est exact.
_FACT_CHECK_RE = re.compile(
    r"("
    r"c\s*est vrai|il parait|parait[- ]il|vraiment vrai|"
    r"\bcombien\b|depuis quand|qui a gagne|"
    r"\bverifi\w*|\bsource\b|\bfake\b|\bintox\b"
    r")"
)


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _recent_lines(transcript: str, count: int = 2) -> str:
    """Les derniers messages du salon, marqueur exclu.

    On regarde deux messages et pas un seul : un lien est souvent colle par
    quelqu'un puis commente par un autre ("ca dit quoi ?").
    """
    lines = [
        line
        for line in transcript.splitlines()
        if line.strip() and not line.lstrip().startswith(">>>")
    ]
    return "\n".join(lines[-count:])


def needs_web_search(transcript: str, directive: str = "") -> bool:
    """Vrai si les derniers messages appellent une info fraiche ou verifiable.

    La consigne eventuelle est analysee elle aussi : "parle du dernier sondage"
    doit activer la recherche meme si le salon n'en parlait pas.
    """
    window = _recent_lines(transcript)
    if directive:
        window = window + "\n" + directive
    window = _strip_accents(window).lower()
    return bool(
        _URL_RE.search(window) or _FRESHNESS_RE.search(window) or _FACT_CHECK_RE.search(window)
    )
