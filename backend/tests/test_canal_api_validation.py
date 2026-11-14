from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_canal_api_contract_routes_are_registered():
    schema = client.get("/openapi.json").json()

    assert "/api/v1/canals" in schema["paths"]
    assert "get" in schema["paths"]["/api/v1/canals"]
    assert "post" in schema["paths"]["/api/v1/canals"]
    assert "get" in schema["paths"]["/api/v1/canals/{canal_id}/supply"]
    assert "put" in schema["paths"]["/api/v1/canals/{canal_id}/supply"]
    assert "get" in schema["paths"]["/api/v1/canals/{canal_id}/demand"]
    assert "post" in schema["paths"]["/api/v1/canals/{canal_id}/coordinate"]


def test_canal_creation_requires_valid_geometry():
    response = client.post("/api/v1/canals", json={"name": "Demo canal"})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["errors"]


def test_supply_schedule_rejects_duplicate_decades_as_problem_json():
    response = client.post(
        "/api/v1/canals/00000000-0000-0000-0000-000000000000/supply",
        json={
            "season": 2027,
            "decades": [
                {"decade": 1, "volume_m3": 100},
                {"decade": 1, "volume_m3": 0},
            ],
        },
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert any("once" in error["msg"] for error in response.json()["errors"])
