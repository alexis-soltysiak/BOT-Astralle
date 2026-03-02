import os

os.environ.setdefault("SCHEDULER_ENABLED", "false")

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_admin_login_session_logout(monkeypatch) -> None:
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "session-secret")
    get_settings.cache_clear()

    client = TestClient(app)

    login = client.post("/auth/login", json={"username": "admin", "password": "secret"})
    assert login.status_code == 200
    assert login.json()["authenticated"] is True

    session = client.get("/auth/session")
    assert session.status_code == 200
    assert session.json()["username"] == "admin"

    logout = client.post("/auth/logout")
    assert logout.status_code == 204

    session_after_logout = client.get("/auth/session")
    assert session_after_logout.status_code == 401


def test_admin_login_rejects_invalid_credentials(monkeypatch) -> None:
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "session-secret")
    get_settings.cache_clear()

    client = TestClient(app)
    login = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert login.status_code == 401
