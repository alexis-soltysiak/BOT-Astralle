from __future__ import annotations

import httpx
import structlog

from app.features.personas.registry import Persona

_TASK_INSTRUCTIONS = """
Tu viens d'ouvrir le salon Discord ci-dessous. Les messages sont donnes du plus
ancien au plus recent.

Reagis au DERNIER message, celui qui est marque comme tel. C'est lui le sujet.
Les messages precedents ne sont la que si tu as besoin de comprendre de quoi il
retourne : la plupart du temps le dernier message se suffit a lui-meme et tu
peux ignorer tout le reste. Ne fais surtout pas une synthese de la conversation
et ne reponds pas a plusieurs messages a la fois.

Quand quelqu'un a colle un lien, son contenu est deja resume entre crochets
apres l'URL, sous la forme [contenu du lien -> ...]. C'est le tweet, l'article
ou la video. Reagis a ce contenu, jamais a l'URL elle-meme, et ne dis jamais
"ton lien" ni "l'article que tu as partage" : tu l'as lu, point.

Si le salon parle d'un sujet d'actualite sur lequel une information recente
change ce que tu dirais, ou si un lien est cite sans que son contenu suffise a
comprendre, cherche sur le web avant de repondre. Sinon ne cherche pas, reponds
directement.

Si le dernier message ne t'inspire vraiment rien, rebondis sur un detail, une
formulation, un mot. Tu ne reponds jamais que tu n'as rien a dire.

Cale ta longueur sur celle du salon. Regarde comment les gens ecrivent
au-dessus : s'ils font une ligne, tu fais une ligne. Un message long te
trahirait immediatement.

Si le dernier message fait le beau, se vante ou dit une betise, remets son
auteur a sa place en une phrase, avec ironie et sans jamais l'insulter.

Cale aussi ton niveau de serieux sur celui du salon. Si ca deconne, tu
deconnes. Ne transforme pas une vanne en tribune politique et ne place une
vraie position que si le sujet la reclame vraiment. Si ta phrase pourrait finir
sur une affiche de campagne, trouve autre chose.

Il se peut qu'une autre personnalite politique soit deja intervenue dans le
salon plus haut. Traite-la comme n'importe quel autre participant : tu peux
lui repondre, la contredire ou la vanner directement, exactement comme tu le
ferais en plateau. Ne fais jamais semblant de ne pas la voir, et ne commente
jamais le fait qu'elle soit la.

Ecris uniquement le message que tu postes dans le salon. Rien d'autre : pas de
guillemets autour, pas de nom devant, pas de commentaire.
""".strip()


def build_input(transcript: str) -> str:
    return f"{_TASK_INSTRUCTIONS}\n\n--- salon Discord ---\n{transcript}"


def with_prior_replies(transcript: str, replies: list[tuple[str, str]]) -> str:
    """Ajoute au contexte ce que les personnages precedents viennent de dire.

    Utilise par la commande de groupe : tout le monde reagit au meme message
    declencheur, mais chacun voit les prises de parole qui l'ont precede. C'est
    ce qui evite des reponses interchangeables et cree un vrai debat, pour un
    cout en tokens negligeable (quelques dizaines de mots).
    """
    if not replies:
        return transcript
    said = "\n".join(f"{name}: {text}" for name, text in replies)
    return (
        f"{transcript}\n\n"
        "--- ont deja reagi juste avant toi, dans l'ordre ---\n"
        f"{said}\n\n"
        "Tu parles apres eux. Ne repete pas ce qui vient d'etre dit et ne le "
        "reformule pas autrement : prends un autre angle, ou reponds "
        "directement a l'un d'eux en le nommant."
    )


def _extract_text(payload: dict) -> str | None:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    output = payload.get("output")
    if not isinstance(output, list):
        return None

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "output_text":
                continue
            text = str(block.get("text") or "").strip()
            if text:
                parts.append(text)

    joined = "\n".join(parts).strip()
    return joined or None


class PersonaClient:
    def __init__(
        self,
        *,
        enabled: bool,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        web_search_enabled: bool = True,
        max_output_tokens: int = 32000,
        reasoning_effort: str = "low",
    ) -> None:
        self._enabled = enabled and bool(api_key.strip())
        self._model = model.strip()
        self._web_search_enabled = web_search_enabled
        self._max_output_tokens = max_output_tokens
        self._reasoning_effort = reasoning_effort.strip().lower()
        self._log = structlog.get_logger("personas")
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

    @property
    def enabled(self) -> bool:
        return self._client is not None and bool(self._model)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    def _build_tools(self, web_search: bool) -> list[dict]:
        if not web_search:
            return []
        return [
            {
                "type": "web_search",
                "search_context_size": "medium",
                "user_location": {
                    "type": "approximate",
                    "country": "FR",
                    "timezone": "Europe/Paris",
                },
            }
        ]

    async def generate(
        self,
        persona: Persona,
        transcript: str,
        *,
        web_search: bool | None = None,
    ) -> str | None:
        if self._client is None or not self._model:
            return None

        # max_output_tokens couvre AUSSI les tokens de raisonnement. Un plafond
        # serre fait rendre un status "incomplete" avec un message vide : le
        # modele a tout depense a reflechir. On laisse donc large, la longueur
        # reelle du message est bornee par la persona, pas par ce chiffre.
        body: dict = {
            "model": self._model,
            "instructions": persona.load_prompt(),
            "input": build_input(transcript),
            "max_output_tokens": self._max_output_tokens,
        }
        if self._reasoning_effort and self._reasoning_effort != "none":
            body["reasoning"] = {"effort": self._reasoning_effort}
        allow_search = self._web_search_enabled if web_search is None else web_search
        tools = self._build_tools(allow_search)
        if tools:
            body["tools"] = tools

        try:
            response = await self._client.post("/responses", json=body)
            response.raise_for_status()
        except Exception as e:
            self._log.warning("persona_request_failed", persona=persona.key, error=str(e))
            return None

        try:
            payload = response.json()
        except Exception as e:
            self._log.warning("persona_parse_failed", persona=persona.key, error=str(e))
            return None

        text = _extract_text(payload)
        if text:
            return text

        # Pas de texte : on veut savoir pourquoi plutot que d'echouer en silence.
        status = payload.get("status")
        incomplete = payload.get("incomplete_details")
        usage = payload.get("usage") or {}
        self._log.warning(
            "persona_empty_output",
            persona=persona.key,
            status=status,
            reason=(incomplete or {}).get("reason") if isinstance(incomplete, dict) else None,
            output_tokens=usage.get("output_tokens"),
            reasoning_tokens=(usage.get("output_tokens_details") or {}).get("reasoning_tokens"),
            max_output_tokens=self._max_output_tokens,
        )
        return None
