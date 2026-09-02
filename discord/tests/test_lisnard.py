from __future__ import annotations

from types import SimpleNamespace

from app.features.lisnard.client import _extract_text, build_input, load_persona
from app.features.lisnard.commands import (
    _LAST_MARKER,
    build_transcript,
    clean_reply,
    extract_message_text,
    reply_context,
)


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
    assert clean_reply("David Lisnard : on marche sur la tete.") == "on marche sur la tete."
    assert clean_reply("Lisnard- bref.") == "bref."


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
