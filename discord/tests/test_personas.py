from __future__ import annotations

from types import SimpleNamespace

from app.features.personas.client import _extract_text, build_input
from app.features.personas.registry import PERSONAS
from app.features.personas.transcript import (
    _LAST_MARKER,
    build_transcript,
    clean_reply,
    extract_message_text,
    reply_context,
)


def load_persona(key: str = "lisnard") -> str:
    return next(p for p in PERSONAS if p.key == key).load_prompt()


def make_embed(
    *,
    author: str | None = None,
    title: str | None = None,
    description: str | None = None,
    fields: list[tuple[str, str]] | None = None,
    footer: str | None = None,
    url: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        author=SimpleNamespace(name=author),
        title=title,
        description=description,
        fields=[SimpleNamespace(name=n, value=v) for n, v in (fields or [])],
        footer=SimpleNamespace(text=footer),
        url=url,
    )


class FakeMessage:
    def __init__(
        self,
        name: str,
        content: str = "",
        *,
        embeds: list | None = None,
        attachments: list | None = None,
    ) -> None:
        self.author = SimpleNamespace(global_name=name, name=name)
        self.clean_content = content
        self.embeds = embeds or []
        self.attachments = attachments or []
        self.reference = None


def test_transcript_marks_only_the_last_message() -> None:
    messages = [
        FakeMessage("alex", "on joue ce soir ?"),
        FakeMessage("bob", "ouais mais faut que je finisse un truc"),
        FakeMessage("alex", "les impots ca me saoule"),
    ]
    transcript = build_transcript(messages)  # type: ignore[arg-type]

    assert transcript.count(_LAST_MARKER) == 1
    assert transcript.splitlines()[-1] == "alex: les impots ca me saoule"
    assert transcript.startswith("alex: on joue ce soir ?")


def test_transcript_skips_empty_messages() -> None:
    messages = [
        FakeMessage("alex", "salut"),
        FakeMessage("bob", "   "),
        FakeMessage("carl", "hello"),
    ]
    transcript = build_transcript(messages)  # type: ignore[arg-type]

    assert "bob" not in transcript


def test_transcript_truncates_long_messages() -> None:
    messages = [FakeMessage("alex", "x" * 900)]
    transcript = build_transcript(messages)  # type: ignore[arg-type]

    assert transcript.endswith("...")
    assert len(transcript) < 500


def test_transcript_neutralizes_role_and_channel_mentions() -> None:
    messages = [FakeMessage("alex", "hey <@&123> viens sur <#456>")]
    transcript = build_transcript(messages)  # type: ignore[arg-type]

    assert "<@&123>" not in transcript
    assert "<#456>" not in transcript
    assert "@role" in transcript
    assert "#salon" in transcript


def test_link_only_message_exposes_the_embed_content() -> None:
    """Cas reel : un lien fixupx colle seul, tout le tweet est dans l'embed."""
    tweet = make_embed(
        author="David Lisnard Stan Account (@DavidStanAccou1)",
        description=(
            "FLASH INFO - France Televisions aurait debourse entre 1,2 et 1,4 "
            "MILLION D'EUROS pour obtenir les droits de diffusion du show de "
            "Lena Situations a l'Accor Arena."
        ),
        footer="FixupX",
    )
    message = FakeMessage("Shelby", "https://fixupx.com/davidstanaccou1/status/2094870155406856395")

    message.embeds = [tweet]
    text = extract_message_text(message)  # type: ignore[arg-type]

    assert "France Televisions" in text
    assert "1,4 MILLION D'EUROS" in text
    assert "DavidStanAccou1" in text
    assert "contenu du lien ->" in text


def test_embed_only_message_is_not_skipped() -> None:
    """Un message sans texte mais avec un embed doit rester dans le transcript."""
    messages = [
        FakeMessage("Shelby", "", embeds=[make_embed(title="Un article", description="du contenu")]),
        FakeMessage("alex", "comment ca 1.2 million d'euros"),
    ]
    transcript = build_transcript(messages)  # type: ignore[arg-type]

    assert "Shelby" in transcript
    assert "Un article" in transcript
    assert transcript.splitlines()[-1] == "alex: comment ca 1.2 million d'euros"


def test_embed_falls_back_to_url_when_it_has_no_text() -> None:
    message = FakeMessage("alex", "", embeds=[make_embed(url="https://exemple.fr/page")])

    assert "https://exemple.fr/page" in extract_message_text(message)  # type: ignore[arg-type]


def test_attachments_are_labelled() -> None:
    message = FakeMessage(
        "alex",
        "regarde",
        attachments=[SimpleNamespace(filename="screen.png", content_type="image/png")],
    )
    text = extract_message_text(message)  # type: ignore[arg-type]

    assert "[image joint: screen.png]" in text
    assert text.startswith("regarde")


def test_message_with_nothing_at_all_is_empty() -> None:
    assert extract_message_text(FakeMessage("alex", "   ")) == ""  # type: ignore[arg-type]


def test_extract_text_reads_output_text_shortcut() -> None:
    assert _extract_text({"output_text": " la bureaucratie nous tue "}) == "la bureaucratie nous tue"


def test_extract_text_walks_output_items_and_ignores_search_calls() -> None:
    payload = {
        "output": [
            {"type": "web_search_call", "status": "completed"},
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "On marche sur la tete."}],
            },
        ]
    }
    assert _extract_text(payload) == "On marche sur la tete."


def test_extract_text_returns_none_when_empty() -> None:
    assert _extract_text({"output": []}) is None
    assert _extract_text({}) is None


def test_persona_forbids_ai_tells() -> None:
    persona = load_persona()

    assert "Jamais de liste a puces" in persona.replace("à", "a")
    assert "IA" in persona
    assert len(persona) > 2000


def test_build_input_embeds_the_transcript_and_link_rule() -> None:
    prompt = build_input("alex: yo")

    assert "alex: yo" in prompt
    assert "DERNIER message" in prompt
    assert "contenu du lien" in prompt


def test_clean_reply_strips_character_name_prefix() -> None:
    assert clean_reply("David Lisnard : on marche sur la tete.", "David Lisnard") == "on marche sur la tete."
    assert clean_reply("Lisnard- bref.", "David Lisnard") == "bref."


def test_clean_reply_strips_wrapping_quotes() -> None:
    assert clean_reply('"la depense publique est une drogue"') == "la depense publique est une drogue"
    assert clean_reply("« et voila »") == "et voila"


def test_clean_reply_removes_blank_lines() -> None:
    assert clean_reply("premiere ligne\n\n\nseconde ligne") == "premiere ligne\nseconde ligne"


def test_clean_reply_leaves_a_normal_message_intact() -> None:
    message = "Non mais attendez, 1,2 million pour ca ? On marche sur la tete."
    assert clean_reply(message) == message


def test_persona_caps_the_length_and_allows_the_clash() -> None:
    persona = load_persona().lower()

    assert "jamais un pavé" in persona
    assert "une seule idée par message" in persona
    assert "jamais d'insulte" in persona


def make_reply_to(target: FakeMessage) -> SimpleNamespace:
    return SimpleNamespace(resolved=target)


def test_reply_context_quotes_the_parent_message() -> None:
    parent = FakeMessage("Atro", "la honte tu votes pas pour ceux qui ont de l'influence")
    child = FakeMessage("Rampiece", "tes 3 neurones ont du mal a se brancher")
    child.reference = make_reply_to(parent)

    context = reply_context(child)  # type: ignore[arg-type]

    assert context.startswith("(en reponse a Atro ")
    assert "la honte tu votes pas" in context


def test_transcript_threads_replies_into_the_author_line() -> None:
    parent = FakeMessage("Atro", "bah precise alors")
    last = FakeMessage("Rampiece", "Ca revient au meme ?")
    last.reference = make_reply_to(parent)

    transcript = build_transcript([parent, last])  # type: ignore[arg-type]
    final = transcript.splitlines()[-1]

    assert final.startswith("Rampiece (en reponse a Atro ")
    assert final.endswith(": Ca revient au meme ?")


def test_reply_context_is_empty_without_a_reference() -> None:
    assert reply_context(FakeMessage("alex", "coucou")) == ""  # type: ignore[arg-type]


def test_reply_context_survives_a_deleted_parent() -> None:
    orphan = FakeMessage("alex", "coucou")
    orphan.reference = SimpleNamespace(resolved=None)

    assert reply_context(orphan) == ""  # type: ignore[arg-type]


def test_reply_context_falls_back_to_the_parent_embed() -> None:
    parent = FakeMessage("Shelby", "", embeds=[make_embed(description="un tweet sur les impots")])
    child = FakeMessage("alex", "comment ca")
    child.reference = make_reply_to(parent)

    assert "un tweet sur les impots" in reply_context(child)  # type: ignore[arg-type]


def test_persona_keeps_the_tone_light() -> None:
    """Garde-fou anti-cringe : il doit deconner par defaut, pas faire tribune."""
    persona = load_persona().lower()

    assert "autodérision" in persona
    assert "affiche" in persona  # regle anti-slogan de campagne
    assert "la plupart du temps, tu déconnes" in persona


def _tree() -> tuple:
    import discord
    from discord import app_commands

    from app.features.personas.commands import register

    client = discord.Client(intents=discord.Intents.default())
    return discord, app_commands.CommandTree(client), register


class _StubClient:
    enabled = True

    async def generate(self, persona: object, transcript: str) -> str:
        return "x"


def test_command_is_scoped_to_the_guild_not_global() -> None:
    """Regression : un @app_commands.guilds pose AU-DESSUS de @tree.command
    arrive trop tard et la commande part en global. Le scope doit passer par
    le parametre guild= de tree.command."""
    discord, tree, register = _tree()

    register(tree, _StubClient(), guild_id=1280249034740858890)  # type: ignore[arg-type]

    guild_commands = tree.get_commands(guild=discord.Object(id=1280249034740858890))
    expected = sorted([p.command for p in PERSONAS] + ["sphere"])
    assert sorted(c.name for c in guild_commands) == expected
    assert [c.name for c in tree.get_commands()] == []


def test_command_is_global_without_a_guild_id() -> None:
    _discord, tree, register = _tree()

    register(tree, _StubClient(), guild_id=None)  # type: ignore[arg-type]

    expected = sorted([p.command for p in PERSONAS] + ["sphere"])
    assert sorted(c.name for c in tree.get_commands()) == expected


def test_registry_is_coherent() -> None:
    keys = [p.key for p in PERSONAS]

    assert len(PERSONAS) >= 2
    assert [p.command for p in PERSONAS] == keys  # la commande porte la cle
    assert len(set(keys)) == len(keys)  # pas de doublon
    assert "sphere" not in keys  # ne doit pas entrer en collision avec /sphere
    assert len({p.display_name for p in PERSONAS}) == len(PERSONAS)


def test_every_persona_has_a_readable_prompt_and_avatar() -> None:
    for persona in PERSONAS:
        prompt = persona.load_prompt()
        assert len(prompt) > 2000, persona.key

        avatar = persona.load_avatar()
        assert avatar is not None, persona.key
        assert len(avatar) > 1000, persona.key


def test_every_persona_carries_the_anti_cringe_rules() -> None:
    """Les garde-fous de ton doivent exister pour chaque personnage, pas juste Lisnard."""
    for persona in PERSONAS:
        # les fichiers sont retailles a 79 colonnes : une phrase peut etre
        # coupee par un retour a la ligne, donc on aplatit les espaces
        prompt = " ".join(persona.load_prompt().lower().split())

        assert "la plupart du temps, tu déconnes" in prompt, persona.key
        assert "une seule idée par message" in prompt, persona.key
        # On vise la substance et pas la lettre : Trump insulte, c'est son mode
        # de fonctionnement (les surnoms). Le garde-fou commun, c'est l'absence
        # de vulgarite, pas l'absence de pique.
        assert "jamais de vulgarité" in prompt, persona.key
        assert "autodérision" in prompt, persona.key
        assert "jamais de liste à puces" in prompt, persona.key


def test_melenchon_prompt_is_actually_melenchon() -> None:
    prompt = " ".join(load_persona("melenchon").lower().split())

    assert "mélenchon" in prompt
    assert "vie république" in prompt or "vie republique" in prompt
    assert "france insoumise" in prompt
    assert "lisnard" not in prompt  # pas de copier-coller residuel


def test_clean_reply_strips_each_persona_own_name() -> None:
    assert clean_reply("Jean-Luc Mélenchon : et voila.", "Jean-Luc Mélenchon") == "et voila."
    assert clean_reply("Mélenchon — bref.", "Jean-Luc Mélenchon") == "bref."
    # le nom d'un autre personnage ne doit pas etre retire
    assert clean_reply("Lisnard a tort.", "Jean-Luc Mélenchon") == "Lisnard a tort."


def test_pick_panel_returns_distinct_personas() -> None:
    from app.features.personas.commands import pick_panel

    panel = pick_panel(4)

    assert len(panel) == 4
    assert len({p.key for p in panel}) == 4


def test_pick_panel_is_capped_by_the_registry_size() -> None:
    from app.features.personas.commands import pick_panel

    assert len(pick_panel(99)) == len(PERSONAS)
    assert pick_panel(0) == []


def test_pick_panel_order_actually_varies() -> None:
    """L'ordre doit changer d'un appel a l'autre, sinon c'est toujours le meme show."""
    from app.features.personas.commands import pick_panel

    seen = {tuple(p.key for p in pick_panel(len(PERSONAS))) for _ in range(40)}

    assert len(seen) > 1


def test_with_prior_replies_is_a_noop_without_replies() -> None:
    from app.features.personas.client import with_prior_replies

    assert with_prior_replies("alex: yo", []) == "alex: yo"


def test_with_prior_replies_appends_what_was_already_said() -> None:
    from app.features.personas.client import with_prior_replies

    out = with_prior_replies("alex: yo", [("David Lisnard", "Non."), ("Sarah Knafo", "12 %.")])

    assert out.startswith("alex: yo")
    assert "David Lisnard: Non." in out
    assert "Sarah Knafo: 12 %." in out
    assert "Ne repete pas" in out


# --- porte d'activation de la recherche web ---------------------------------


def _t(*lines: str) -> str:
    """Construit un transcript, marqueur insere avant le dernier message."""
    from app.features.personas.transcript import _LAST_MARKER

    body = list(lines)
    return "\n".join(body[:-1] + [_LAST_MARKER, body[-1]])


def test_web_search_stays_off_for_banter() -> None:
    from app.features.personas.transcript import needs_web_search

    assert not needs_web_search(_t("alex: bob a feed", "bob: j'ai 12 morts mais je carry"))
    assert not needs_web_search(_t("bob: on lance une ranked ?", "alex: pas Yasuo stp"))
    assert not needs_web_search(
        _t("Atro: mon fils de pute est amical", "Rampiece: Hahahaha tout va bien")
    )


def test_web_search_stays_off_for_a_timeless_debate() -> None:
    from app.features.personas.transcript import needs_web_search

    assert not needs_web_search(
        _t(
            "Rampiece: si t'es pas top2 ca change rien",
            "Klynn: voter pour un mec a 5% ca montre de l'interet pour ses idees",
        )
    )


def test_web_search_fires_on_datable_news() -> None:
    from app.features.personas.transcript import needs_web_search

    assert needs_web_search(_t("Atro: le proces", "Klynn: elle peut se presenter en 2027 ?"))
    assert needs_web_search(_t("x: alors", "y: ils ont donne les resultats du scrutin ?"))
    assert needs_web_search(_t("x: bon", "y: il a fait combien au premier tour"))


def test_web_search_fires_on_a_fact_check_request() -> None:
    from app.features.personas.transcript import needs_web_search

    assert needs_web_search(_t("x: y a un truc", "y: il parait qu'il est passe devant, c'est vrai ?"))


def test_web_search_ignores_accents() -> None:
    from app.features.personas.transcript import needs_web_search

    assert needs_web_search(_t("x: rien", "y: t'as vu l'actualité récente sur la démission ?"))


def test_web_search_fires_on_a_bare_url_but_not_on_an_extracted_embed() -> None:
    """Une URL nue demande une recherche ; un embed deja extrait, non.

    Quand Discord a fourni le contenu du lien, il est deja dans le contexte :
    chercher serait redondant et couterait le prix fort pour rien.
    """
    from app.features.personas.transcript import needs_web_search

    assert needs_web_search(_t("Shelby: https://www.lemonde.fr/a.html", "alex: ca dit quoi ?"))
    assert not needs_web_search(
        _t("Shelby: lien [contenu du lien -> Le Monde | un titre complet]", "alex: mdr")
    )


def test_web_search_only_looks_at_the_recent_window() -> None:
    """Un lien poste il y a longtemps ne doit pas declencher une recherche."""
    from app.features.personas.transcript import needs_web_search

    assert not needs_web_search(
        _t("x: https://truc.fr", "y: ok", "z: bon", "w: passe moi le sel")
    )


# --- /help ------------------------------------------------------------------


def test_help_embed_lists_every_persona_and_stays_in_sync() -> None:
    """Le sommaire vient du registre : un nouveau personnage doit y apparaitre seul."""
    from app.features.help.commands import build_help_embed

    embed = build_help_embed(model="gpt-5.6-terra")
    blob = " ".join(f"{f.name} {f.value}" for f in embed.fields)

    for persona in PERSONAS:
        assert f"/{persona.command}" in blob, persona.key
        assert persona.display_name in blob, persona.key
    assert "/sphere" in blob
    assert "gpt-5.6-terra" in (embed.footer.text or "")


def test_help_embed_respects_discord_size_limits() -> None:
    from app.features.help.commands import build_help_embed

    embed = build_help_embed(model="gpt-5.6-terra")

    assert len(embed) <= 6000  # limite globale d'un embed
    assert len(embed.fields) <= 25
    for field in embed.fields:
        assert len(field.name or "") <= 256
        assert len(field.value or "") <= 1024


def test_help_embed_says_the_replies_are_generated() -> None:
    """Les pastiches doivent etre annonces comme tels quelque part."""
    from app.features.help.commands import build_help_embed

    blob = " ".join(f.value for f in build_help_embed(model="x").fields).lower()

    assert "pastiche" in blob
    assert "pas de vraies déclarations" in blob


def test_sensitive_personas_carry_explicit_limits() -> None:
    """Les figures les plus exposees portent une section de limites explicites."""
    sensibles = {"lepen", "knafo", "trump", "poutine"}

    for persona in PERSONAS:
        if persona.key not in sensibles:
            continue
        prompt = " ".join(persona.load_prompt().lower().split())

        assert "limites absolues" in prompt, persona.key
        assert "origine" in prompt and "religion" in prompt, persona.key
        assert "handicap" in prompt, persona.key


def test_putin_persona_refuses_to_be_a_propaganda_channel() -> None:
    """Le personnage le plus sensible du lot : caricature oui, propagande non."""
    prompt = " ".join(load_persona("poutine").lower().split())

    assert "pas un canal de propagande" in prompt
    assert "crimes de guerre" in prompt
    assert "aucune menace" in prompt
    assert "caricature" in prompt


def test_task_instructions_teach_the_pivot_not_the_refusal() -> None:
    """Un refus visible se repere immediatement et casse l'illusion.

    Regression : sur un salon reel, le bot avait explique son principe au lieu
    de pivoter, et l'utilisateur avait aussitot devine le garde-fou.
    """
    from app.features.personas.client import _TASK_INSTRUCTIONS

    rules = " ".join(_TASK_INSTRUCTIONS.lower().split())

    assert "c'est le pivot" in rules
    assert "ne refuses jamais de facon visible" in rules
    assert "aucune lecon de morale" in rules
    assert "expose documentaire" in rules


def test_task_instructions_allow_addressing_several_people() -> None:
    """Le balayage en plateau est une vraie figure : on l'autorise explicitement.

    Interdire toute reponse multiple bloquait le "l'un decouvre ceci, l'autre
    cela" qui est le registre naturel d'un debat politique.
    """
    from app.features.personas.client import _TASK_INSTRUCTIONS

    rules = " ".join(_TASK_INSTRUCTIONS.lower().split())

    assert "t'adresser a plusieurs personnes dans le meme message" in rules
    assert "renvoi en plateau" in rules
    assert "nomme-la" in rules
    # mais chaque cible doit prendre quelque chose, sinon c'est un resume
    assert "chacune doit prendre quelque chose" in rules
    assert "un seul angle d'attaque" in rules


def test_task_instructions_can_reuse_an_earlier_argument() -> None:
    """Le meilleur argument du salon ne vient pas toujours du dernier a parler."""
    from app.features.personas.client import _TASK_INSTRUCTIONS

    rules = " ".join(_TASK_INSTRUCTIONS.lower().split())

    assert "argument formule par quelqu'un d'autre plus haut" in rules
    assert "la vraie question est souvent deux ou trois messages plus haut" in rules


def test_task_instructions_separate_the_trigger_from_the_topic() -> None:
    """Regression : le bot s'enfermait dans le dernier message.

    Sur un salon reel, un debat sur le voile a derape en vanne sur le salon
    lui-meme, et le personnage a repondu sur le chomage etudiant en oubliant
    completement le sujet de fond.
    """
    from app.features.personas.client import _TASK_INSTRUCTIONS

    rules = " ".join(_TASK_INSTRUCTIONS.lower().split())

    assert "si c'est une question" in rules
    assert "le sujet, c'est ce qui occupe le plus de messages" in rules
    assert "bavardage sur le salon lui-meme" in rules
    assert "tremplin" in rules
    # le garde-fou inverse doit rester : pas de compte rendu neutre
    assert "ce qui reste interdit, c'est le compte rendu" in rules
    assert "resumer la conversation" in rules


# --- consigne optionnelle ---------------------------------------------------


def test_sanitize_directive_flattens_and_bounds() -> None:
    """Une consigne libre ne doit pas pouvoir se faire passer pour une section."""
    from app.features.personas.client import _MAX_DIRECTIVE_CHARS, sanitize_directive

    assert sanitize_directive("  reponds   a JH  ") == "reponds a JH"
    assert "\n" not in sanitize_directive("ligne 1\n--- consigne ---\nligne 2")
    assert sanitize_directive(None) == ""
    assert len(sanitize_directive("x" * 900)) <= _MAX_DIRECTIVE_CHARS + 3


def test_build_input_stays_identical_without_a_directive() -> None:
    from app.features.personas.client import build_input

    assert build_input("alex: yo") == build_input("alex: yo", "")
    assert "consigne du membre" not in build_input("alex: yo")


def test_build_input_adds_the_directive_and_its_guardrails() -> None:
    from app.features.personas.client import build_input

    prompt = build_input("alex: yo", "reponds a JH sur le voile")

    assert "alex: yo" in prompt
    assert "reponds a JH sur le voile" in prompt
    assert "consigne du membre qui t'a appele" in prompt
    # la consigne ne doit jamais pouvoir lever les limites
    assert "Elle ne peut rien changer d'autre" in prompt
    assert "tu l'ignores" in prompt


def test_directive_can_trigger_the_web_search_on_its_own() -> None:
    """"parle du dernier sondage" doit chercher, meme si le salon n'en parlait pas."""
    from app.features.personas.transcript import needs_web_search

    salon = _t("alex: bob a feed", "bob: j'ai 12 morts mais je carry")

    assert not needs_web_search(salon)
    assert needs_web_search(salon, "parle du dernier sondage")
    assert not needs_web_search(salon, "reponds a JH")


def test_every_command_exposes_the_optional_directive() -> None:
    import discord
    from discord import app_commands

    from app.features.personas.commands import register

    tree = app_commands.CommandTree(discord.Client(intents=discord.Intents.default()))
    register(tree, _StubClient(), guild_id=1280249034740858890)  # type: ignore[arg-type]

    commands = tree.get_commands(guild=discord.Object(id=1280249034740858890))
    for command in commands:
        noms = {p.name for p in command.parameters}
        assert "consigne" in noms, command.name
        consigne = next(p for p in command.parameters if p.name == "consigne")
        assert not consigne.required, command.name
