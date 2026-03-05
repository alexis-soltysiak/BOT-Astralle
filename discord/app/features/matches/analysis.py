from __future__ import annotations

import json
import re

import discord
import httpx
import structlog

from app.features.matches.embeds import build_match_analysis_context


_ANALYSIS_LIMITS = {"strengths": 3, "improvements": 3, "next_steps": 2}
_TAG_PATTERN = re.compile(r"^\s*\[(global|vs_opponent|objectives|team|role)\]\s*(.+)$", re.IGNORECASE)
_TAG_LABELS = {
    "global": "Global",
    "vs_opponent": "Vs Opponent",
    "objectives": "Objectives",
    "team": "Team",
    "role": "Role",
}
_TAG_EMOJIS = {
    "global": "🌐",
    "vs_opponent": "⚔️",
    "objectives": "🎯",
    "team": "👥",
    "role": "🎮",
}


def _role_guidance(role: object) -> str:
    value = str(role or "").strip().upper()
    if value == "TOP":
        return "Analyse surtout wave control, trades, side lane, TP et pression solo."
    if value == "JUNGLE":
        return "Analyse surtout pathing, tempo camps, objectifs, ganks, cover lanes et vision."
    if value == "MID":
        return "Analyse surtout priorite lane, trades, roam, setup vision et impact sur objectifs."
    if value == "ADC":
        return "Analyse surtout farm, positionnement teamfight, spikes items, DPS et survie."
    if value == "SUPPORT":
        return "Analyse surtout vision, timings roam, setup engage/peel, lane pressure et protection carry."
    return "Analyse surtout l'impact de role, le tempo et l'execution macro."


def _category_rank_map(context: dict | None) -> dict[str, int]:
    if not isinstance(context, dict):
        return {}
    details = context.get("category_details")
    if not isinstance(details, list):
        return {}
    out: dict[str, int] = {}
    for row in details:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip().lower()
        rank = row.get("rank")
        if key and isinstance(rank, int):
            out[key] = rank
    return out


def _parse_tagged_line(text: str) -> tuple[str, str] | None:
    match = _TAG_PATTERN.match(text)
    if not match:
        return None
    key = str(match.group(1)).strip().lower()
    body = " ".join(str(match.group(2) or "").split())
    if not body:
        return None
    return key, body


def _render_advice_line(text: object) -> str | None:
    line = _normalize_line(text, limit=220)
    if not line:
        return None
    parsed = _parse_tagged_line(line)
    if parsed is None:
        return line
    key, body = parsed
    label = _TAG_LABELS.get(key, key)
    emoji = _TAG_EMOJIS.get(key, "•")
    return f"{emoji} **{label}** {body}"


def _normalize_tagged_list(
    items: object,
    *,
    context: dict | None,
    max_items: int,
    mode: str,
) -> list[str]:
    if not isinstance(items, list):
        return []
    ranks = _category_rank_map(context)
    out: list[str] = []
    for item in items:
        line = _normalize_line(item, limit=220)
        if not line:
            continue
        parsed = _parse_tagged_line(line)
        if parsed is None:
            continue
        key, body = parsed
        rank = ranks.get(key)
        if rank is None:
            continue
        if mode == "strengths" and rank > 4:
            continue
        if mode in {"improvements", "next_steps"} and rank < 7:
            continue
        out.append(f"[{key}] {body}")
        if len(out) >= max_items:
            break
    return out


def _build_prompt(context: dict) -> str:
    category_lines: list[str] = []
    for category in context.get("category_details") or []:
        metrics = category.get("metrics") or []
        metrics_text = ", ".join(
            f"{metric.get('label')}: value={metric.get('value')} pts={metric.get('points'):+}"
            for metric in metrics
            if isinstance(metric, dict)
        )
        category_lines.append(
            f"- {category.get('label')}: rank={category.get('rank')}/10 total={category.get('total_points')} | {metrics_text}"
        )

    ranks = _category_rank_map(context)
    strong = [key for key, rank in ranks.items() if rank <= 4]
    weak = [key for key, rank in ranks.items() if rank >= 7]
    strong_text = ", ".join(strong) if strong else "none"
    weak_text = ", ".join(weak) if weak else "none"
    lines = [
        "Analyse cette performance individuelle League of Legends comme un coach pro tres factuel.",
        "Donne uniquement des constats soutenus par les donnees fournies.",
        "Interdiction d'inventer, d'extrapoler ou de generaliser sans preuve.",
        "Reponds en francais sous forme d'un JSON strict, sans markdown, sans texte autour.",
        "Schema JSON obligatoire:",
        '{"headline":"string","summary":"string","strengths":["string"],"improvements":["string"],"next_steps":["string"],"key_focus":"string","confidence":"low|medium|high"}',
        "Contraintes:",
        '- "headline": 4 a 8 mots max',
        '- "summary": 1 phrase, 22 mots max',
        '- "strengths": 0 a 3 points',
        '- "improvements": 0 a 3 points',
        '- "next_steps": 0 a 2 actions',
        '- "key_focus": 3 a 8 mots',
        '- "confidence": low, medium ou high',
        "Chaque item de strengths/improvements/next_steps doit commencer par un tag parmi [global], [vs_opponent], [objectives], [team], [role].",
        "N'ajoute pas de point si la preuve n'est pas suffisante.",
        "Si aucun point pertinent, renvoie une liste vide [].",
        "Regle de certitude:",
        f"- categories fortes (rank<=4): {strong_text}",
        f"- categories faibles (rank>=7): {weak_text}",
        "- strengths: uniquement categories fortes.",
        "- improvements/next_steps: uniquement categories faibles.",
        _role_guidance(context.get("role")),
        "",
        f"Joueur: {context.get('player_name')}",
        f"Match: {context.get('riot_match_id')}",
        f"Queue: {context.get('queue')} ({context.get('ranked_queue_type')})",
        f"Champion: {context.get('champion')}",
        f"Role: {context.get('role')}",
        f"Resultat: {context.get('result')}",
        f"Duree: {context.get('duration')}",
        f"KDA: {context.get('kda')}",
        f"KP: {context.get('kp')}",
        f"CS: {context.get('cs')}",
        f"Score final: {context.get('final_score')}/100",
        f"Classement final: {context.get('final_rank')}/10",
        f"Contexte LP: {context.get('lp_line') or 'indisponible'}",
        f"Rank before: {context.get('rank_before') or 'indisponible'}",
        f"Rank after: {context.get('rank_after') or 'indisponible'}",
        f"LP delta: {context.get('rank_delta_lp') if context.get('rank_delta_lp') is not None else 'indisponible'}",
        f"Notes resumees: {context.get('notes_summary')}",
        f"Spells: {json.dumps(context.get('spells') or [], ensure_ascii=True)}",
        f"Items: {json.dumps(context.get('items') or [], ensure_ascii=True)}",
        "Notes detaillees:",
        *category_lines,
    ]
    return "\n".join(lines)


def _extract_json_text(raw: str) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return None
    return text[start : end + 1]


def _normalize_line(text: object, *, limit: int = 120) -> str | None:
    value = " ".join(str(text or "").split())
    if not value:
        return None
    if len(value) > limit:
        return value[:limit].rstrip()
    return value


def _normalize_list(items: object, *, limit: int = 3, item_limit: int = 60) -> list[str]:
    if not isinstance(items, list):
        return []
    normalized: list[str] = []
    for item in items:
        line = _normalize_line(item, limit=item_limit)
        if line:
            normalized.append(line)
        if len(normalized) >= limit:
            break
    return normalized


def _normalize_confidence(value: object) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"low", "medium", "high"}:
        return raw
    return "medium"


def _build_recent_form_prompt(payload: dict) -> str:
    player = payload.get("player") or {}
    aggregates = payload.get("aggregates") or {}
    matches = payload.get("matches") or []

    lines: list[str] = []
    for row in matches:
        if not isinstance(row, dict):
            continue
        lines.append(
            (
                f"- {row.get('queue_label')} | {row.get('champion_name') or '?'} | {row.get('role') or '?'} | "
                f"{str(row.get('result') or '').upper()} | score={row.get('final_score')} | rank={row.get('final_rank')}/10 | "
                f"KDA={row.get('kda')} | KP={row.get('kill_participation')} | CS/min={row.get('cs_per_min')} | LP={row.get('rank_delta_lp')}"
            )
        )

    prompt = [
        "Analyse une serie des 20 dernieres games League of Legends comme un analyste pro tres concret.",
        "Reponds en francais avec un JSON strict, sans markdown.",
        "Tu dois te baser sur les tendances globales et les patterns repetes (pas sur 1 seule game).",
        "Schema JSON obligatoire:",
        '{"headline":"string","summary":"string","strengths":["string"],"improvements":["string"],"next_steps":["string"],"key_focus":"string","confidence":"low|medium|high"}',
        "Contraintes:",
        '- "headline": 4 a 8 mots',
        '- "summary": 20 mots max',
        '- "strengths": exactement 3 points',
        '- "improvements": exactement 3 points',
        '- "next_steps": exactement 3 actions claires',
        '- "key_focus": 5 mots max',
        "Style: direct, actionnable, specifique SoloQ/Flex, niveau coach haut elo.",
        "",
        f"Joueur: {player.get('discord_display_name') or player.get('game_name') or 'Unknown'}",
        f"Riot ID: {(player.get('game_name') or '?')}#{(player.get('tag_line') or '?')}",
        f"Games analysees: {aggregates.get('matches_count')}",
        f"Winrate: {aggregates.get('win_rate')}%",
        f"Record: {aggregates.get('wins')}W/{aggregates.get('losses')}L",
        f"Score moyen: {aggregates.get('avg_final_score')}",
        f"Place moyenne: {aggregates.get('avg_final_rank')}/10",
        f"KDA moyen: {aggregates.get('avg_kills')}/{aggregates.get('avg_deaths')}/{aggregates.get('avg_assists')}",
        f"KP moyen: {aggregates.get('avg_kp')}%",
        f"CS/min moyen: {aggregates.get('avg_cs_per_min')}",
        f"LP moyen/game: {aggregates.get('avg_rank_delta_lp')}",
        f"LP total: {aggregates.get('total_rank_delta_lp')}",
        f"Trend score (last5-prev5): {aggregates.get('score_trend_delta')}",
        f"Top champions: {json.dumps(aggregates.get('top_champions') or [], ensure_ascii=True)}",
        f"Role distribution: {json.dumps(aggregates.get('role_distribution') or {}, ensure_ascii=True)}",
        f"Queue distribution: {json.dumps(aggregates.get('queue_distribution') or {}, ensure_ascii=True)}",
        "Timeline recente:",
        *lines[:20],
    ]
    return "\n".join(prompt)


def _normalize_recent_form_payload(raw: str) -> dict | None:
    json_text = _extract_json_text(raw)
    if not json_text:
        return None
    try:
        data = json.loads(json_text)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    headline = _normalize_line(data.get("headline"), limit=72)
    summary = _normalize_line(data.get("summary"), limit=180)
    strengths = _normalize_list(data.get("strengths"), limit=3, item_limit=80)
    improvements = _normalize_list(data.get("improvements"), limit=3, item_limit=80)
    next_steps = _normalize_list(data.get("next_steps"), limit=3, item_limit=80)
    key_focus = _normalize_line(data.get("key_focus"), limit=64)
    confidence = _normalize_confidence(data.get("confidence"))

    if not any([headline, summary, strengths, improvements, next_steps, key_focus]):
        return None

    return {
        "headline": headline or "Bilan sur 20 games",
        "summary": summary or "",
        "strengths": strengths,
        "improvements": improvements,
        "next_steps": next_steps,
        "key_focus": key_focus or "",
        "confidence": confidence,
    }


def _normalize_analysis_payload(raw: str, context: dict | None = None) -> dict | None:
    json_text = _extract_json_text(raw)
    if not json_text:
        return None
    try:
        data = json.loads(json_text)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    headline = _normalize_line(data.get("headline"), limit=64)
    summary = _normalize_line(data.get("summary"), limit=140)
    strengths = _normalize_tagged_list(
        data.get("strengths"),
        context=context,
        max_items=_ANALYSIS_LIMITS["strengths"],
        mode="strengths",
    )
    improvements = _normalize_tagged_list(
        data.get("improvements"),
        context=context,
        max_items=_ANALYSIS_LIMITS["improvements"],
        mode="improvements",
    )
    next_steps = _normalize_tagged_list(
        data.get("next_steps"),
        context=context,
        max_items=_ANALYSIS_LIMITS["next_steps"],
        mode="next_steps",
    )
    key_focus = _normalize_line(data.get("key_focus"), limit=48)

    if not any([headline, summary, strengths, improvements, next_steps, key_focus]):
        return None

    return {
        "headline": headline or "Conseils de progression",
        "summary": summary or "",
        "strengths": strengths,
        "improvements": improvements,
        "next_steps": next_steps,
        "key_focus": key_focus or "",
        "confidence": _normalize_confidence(data.get("confidence")),
    }


def build_match_advice_embed(
    *,
    analysis_payload: dict,
    player_name: str,
    author_name: str | None = None,
    author_icon_url: str | None = None,
    embed_color: discord.Color | None = None,
) -> discord.Embed:
    confidence = str(analysis_payload.get("confidence") or "medium")
    confidence_label = {
        "low": "Confiance faible",
        "medium": "Confiance moyenne",
        "high": "Confiance haute",
    }.get(confidence, "Confiance moyenne")

    embed = discord.Embed(
        title=f"Conseils match - {player_name}",
        description=str(analysis_payload.get("headline") or ""),
        color=embed_color or discord.Color.blurple(),
    )
    if author_name:
        if author_icon_url:
            embed.set_author(name=author_name, icon_url=author_icon_url)
        else:
            embed.set_author(name=author_name)

    strengths = analysis_payload.get("strengths") or []
    if strengths:
        rendered = [line for line in (_render_advice_line(item) for item in strengths) if line]
        if rendered:
            embed.add_field(name="✅ Bien", value="\n".join(f"• {item}" for item in rendered), inline=False)

    improvements = analysis_payload.get("improvements") or []
    if improvements:
        rendered = [line for line in (_render_advice_line(item) for item in improvements) if line]
        if rendered:
            embed.add_field(name="🛠️ A ameliorer", value="\n".join(f"• {item}" for item in rendered), inline=False)

    key_focus = str(analysis_payload.get("key_focus") or "").strip()
    footer = key_focus if key_focus else confidence_label
    if key_focus:
        footer = f"Focus: {key_focus} | {confidence_label}"
    embed.set_footer(text=footer)
    return embed


def build_recent_form_advice_embed(
    *,
    player_name: str,
    aggregates: dict,
    analysis_payload: dict | None,
    author_icon_url: str | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"Analyse PRO - 20 games - {player_name}",
        color=discord.Color.blurple(),
    )
    if author_icon_url:
        embed.set_author(name=player_name, icon_url=author_icon_url)
    else:
        embed.set_author(name=player_name)

    win_rate = aggregates.get("win_rate")
    record = f"{aggregates.get('wins', 0)}W/{aggregates.get('losses', 0)}L"
    perf_line = (
        f"WR **{win_rate}%** | Score **{aggregates.get('avg_final_score')}** | "
        f"Place **{aggregates.get('avg_final_rank')}/10**"
    )
    lp_line = f"LP/game **{aggregates.get('avg_rank_delta_lp')}** | LP total **{aggregates.get('total_rank_delta_lp')}**"
    embed.add_field(name="Snapshot", value=f"{record}\n{perf_line}\n{lp_line}", inline=False)

    if not analysis_payload:
        embed.add_field(
            name="Conseils",
            value="LLM indisponible ou aucune sortie exploitable.",
            inline=False,
        )
        return embed

    summary = str(analysis_payload.get("summary") or "").strip()
    if summary:
        embed.add_field(name="Lecture", value=summary, inline=False)

    strengths = analysis_payload.get("strengths") or []
    if strengths:
        rendered = [line for line in (_render_advice_line(item) for item in strengths) if line]
        if rendered:
            embed.add_field(name="Points forts", value="\n".join(f"- {item}" for item in rendered), inline=False)

    improvements = analysis_payload.get("improvements") or []
    if improvements:
        rendered = [line for line in (_render_advice_line(item) for item in improvements) if line]
        if rendered:
            embed.add_field(name="A corriger", value="\n".join(f"- {item}" for item in rendered), inline=False)

    next_steps = analysis_payload.get("next_steps") or []
    if next_steps:
        rendered = [line for line in (_render_advice_line(item) for item in next_steps) if line]
        if rendered:
            embed.add_field(name="Plan d'action", value="\n".join(f"- {item}" for item in rendered), inline=False)

    key_focus = str(analysis_payload.get("key_focus") or "").strip()
    confidence = str(analysis_payload.get("confidence") or "medium")
    footer = f"Focus: {key_focus}" if key_focus else "Focus: Execution reguliere"
    embed.set_footer(text=f"{footer} | confiance: {confidence}")
    return embed
class MatchAnalysisClient:
    def __init__(
        self,
        *,
        enabled: bool,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self._enabled = enabled and bool(api_key.strip())
        self._model = model.strip()
        self._log = structlog.get_logger("match_analysis")
        self._client: httpx.AsyncClient | None = None
        if self._enabled:
            self._client = httpx.AsyncClient(
                timeout=timeout_seconds,
                headers={
                    "Authorization": f"Bearer {api_key.strip()}",
                    "Content-Type": "application/json",
                },
                base_url=base_url.rstrip("/"),
            )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def generate(
        self,
        summary: dict,
        tracked_by_puuid: dict[str, dict],
        *,
        focus_puuid: str | None = None,
    ) -> dict | None:
        if self._client is None or not self._model:
            return None

        context = build_match_analysis_context(summary, tracked_by_puuid, focus_puuid=focus_puuid)
        if context is None:
            return None

        try:
            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "max_completion_tokens": 1000,
                    "reasoning_effort": "minimal",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Tu es un analyste League of Legends tres factuel. "
                                "Tu donnes un retour utile, specifique au role, structure et actionnable."
                            ),
                        },
                        {
                            "role": "user",
                            "content": _build_prompt(context),
                        },
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
            choices = payload.get("choices")
            if not isinstance(choices, list) or not choices:
                return None
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if not isinstance(message, dict):
                return None
            content = message.get("content")
            if isinstance(content, str):
                return _normalize_analysis_payload(content, context)
            if isinstance(content, list):
                parts = [
                    str(item.get("text") or "").strip()
                    for item in content
                    if isinstance(item, dict) and str(item.get("type") or "") == "text"
                ]
                return _normalize_analysis_payload("\n".join(part for part in parts if part), context)
            return None
        except Exception as e:
            self._log.warning("match_analysis_failed", error=str(e))
            return None

    async def generate_recent_form(self, payload: dict) -> dict | None:
        if self._client is None or not self._model:
            return None

        try:
            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "max_completion_tokens": 1200,
                    "reasoning_effort": "minimal",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Tu es un coach LoL elite. "
                                "Tu fais une analyse de tendances sur 20 games, precise et actionnable."
                            ),
                        },
                        {
                            "role": "user",
                            "content": _build_recent_form_prompt(payload),
                        },
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices")
            if not isinstance(choices, list) or not choices:
                return None
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if not isinstance(message, dict):
                return None
            content = message.get("content")
            if isinstance(content, str):
                return _normalize_recent_form_payload(content)
            if isinstance(content, list):
                parts = [
                    str(item.get("text") or "").strip()
                    for item in content
                    if isinstance(item, dict) and str(item.get("type") or "") == "text"
                ]
                return _normalize_recent_form_payload("\n".join(part for part in parts if part))
            return None
        except Exception as e:
            self._log.warning("recent_form_analysis_failed", error=str(e))
            return None
