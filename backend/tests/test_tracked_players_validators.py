import pytest

from app.features.tracked_players.validators import (
    normalize_discord_display_name,
    normalize_discord_user_id,
    normalize_game_name,
    normalize_tag_line,
    validate_region,
)


def test_normalize_game_name() -> None:
    assert normalize_game_name("  Alexis  ") == "Alexis"
    with pytest.raises(ValueError):
        normalize_game_name("   ")


def test_normalize_tag_line() -> None:
    assert normalize_tag_line("  EUW  ") == "EUW"
    with pytest.raises(ValueError):
        normalize_tag_line("")


def test_validate_region() -> None:
    assert validate_region("EUROPE") == "europe"
    with pytest.raises(ValueError):
        validate_region("euw1")


def test_normalize_discord_user_id() -> None:
    assert normalize_discord_user_id(" 1234567890 ") == "1234567890"
    with pytest.raises(ValueError):
        normalize_discord_user_id("abc")


def test_normalize_discord_display_name() -> None:
    assert normalize_discord_display_name("  alex  ") == "alex"
    assert normalize_discord_display_name("   ") is None
