from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_stub_returns_problem_json():
    r = client.get("/api/v1/data-sources")
    assert r.status_code == 501
    assert r.headers["content-type"].startswith("application/problem+json")
