from app.core.config import get_settings


def test_settings_load() -> None:
    s = get_settings()
    assert isinstance(s.env, str)
