from __future__ import annotations


ALLOWED_REGIONS = {"europe", "americas", "asia", "sea"}

ALLOWED_PLATFORMS = {
    "br1",
    "eun1",
    "euw1",
    "jp1",
    "kr",
    "la1",
    "la2",
    "na1",
    "oc1",
    "tr1",
    "ru",
    "ph2",
    "sg2",
    "th2",
    "tw2",
    "vn2",
}


def normalize_game_name(value: str) -> str:
    v = value.strip()
    if not v:
        raise ValueError("game_name_empty")
    return v


def normalize_tag_line(value: str) -> str:
    v = value.strip()
    if not v:
        raise ValueError("tag_line_empty")
    if len(v) > 16:
        raise ValueError("tag_line_too_long")
    return v


def normalize_discord_user_id(value: str) -> str:
    v = value.strip()
    if not v:
        raise ValueError("discord_user_id_empty")
    if not v.isdigit():
        raise ValueError("discord_user_id_invalid")
    return v


def normalize_discord_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    return v or None


def validate_region(value: str) -> str:
    v = value.strip().lower()
    if v not in ALLOWED_REGIONS:
        raise ValueError("invalid_region")
    return v


def validate_platform(value: str) -> str:
    v = value.strip().lower()
    if v not in ALLOWED_PLATFORMS:
        raise ValueError("invalid_platform")
    return v
