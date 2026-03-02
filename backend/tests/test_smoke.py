import os

os.environ.setdefault("SCHEDULER_ENABLED", "false")

from fastapi.testclient import TestClient

from app.main import app


def test_root_ok() -> None:
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200


def test_healthz_ok() -> None:
    client = TestClient(app)
    res = client.get("/healthz")
    assert res.status_code == 200