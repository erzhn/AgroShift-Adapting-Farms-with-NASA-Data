"""Full HTTP create/read/update/delete and geospatial error-path tests."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import models
from app.db.session import get_db
from app.main import app
from app.modules.farms.demo import FARM_ID, load_seed, seed_id
from app.modules.farms.seed import seed_farms

pytestmark = pytest.mark.db
PREFIX = "/api/v1"


@pytest.fixture
def client(db):
    seed_farms(db)
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def point_field(**updates):
    return {
        "name": "Новое поле",
        "area_ha": 1.5,
        "location": {"type": "Point", "coordinates": [74.31, 42.86]},
        **updates,
    }


def test_partial_season_preserves_yield_and_validates_merged_dates(client):
    farm_url = f"{PREFIX}/farms/{FARM_ID}"
    original = client.get(farm_url).json()["fields"][0]
    season = original["seasons"][0]
    url = f"{farm_url}/fields/{original['id']}"
    body = {
        "season": {
            "crop_variant_id": season["crop_variant_id"],
            "year": season["year"],
            "harvest_date": f"{season['year']}-12-01",
        }
    }
    response = client.patch(url, json=body)
    assert response.status_code == 200, response.text
    updated = response.json()["seasons"][0]
    assert updated["planned_yield_t_ha"] == season["planned_yield_t_ha"]
    assert updated["sowing_date"] == season["sowing_date"]
    body["season"]["harvest_date"] = f"{season['year']}-01-01"
    assert client.patch(url, json=body).status_code == 422
    assert client.get(url).json()["seasons"][0] == updated


def test_farm_and_field_complete_lifecycle(client, db):
    response = client.post(
        f"{PREFIX}/farms",
        json={
            "name": "  Новый фермер  ",
            "cash_som": 0,
            "family_reserve_som": 10000,
            "cow_count": 2,
        },
    )
    assert response.status_code == 201, response.text
    farm = response.json()
    assert farm["name"] == "Новый фермер" and farm["cash_som"] == 0
    farm_url = f"{PREFIX}/farms/{farm['id']}"
    assert client.get(farm_url).json()["herds"][0]["head_count"] == 2
    season = {
        "crop_variant_id": str(seed_id("variant/maize_silage")),
        "year": 2027,
        "sowing_date": "2027-04-25",
        "harvest_date": "2027-08-22",
    }
    response = client.post(f"{farm_url}/fields", json=point_field(season=season))
    assert response.status_code == 201, response.text
    field = response.json()
    field_url = f"{farm_url}/fields/{field['id']}"
    assert field["seasons"][0]["crop_id"] == str(seed_id("crop/maize"))
    assert client.get(f"{farm_url}/fields").json()["features"][0]["geometry"]["type"] == "Point"
    response = client.patch(field_url, json={"name": "Южное", "area_ha": 2})
    assert response.status_code == 200, response.text
    assert client.get(field_url).json()["name"] == "Южное"
    assert client.get(farm_url).json()["area_ha"] == 2
    response = client.patch(farm_url, json={"cash_som": 50000, "cow_count": 3})
    assert response.status_code == 200, response.text
    assert response.json()["cash_som"] == 50000
    assert response.json()["family_reserve_som"] == 10000
    assert response.json()["herds"][0]["provenance"]["head_count"]["source_type"] == "user_estimate"
    assert client.delete(field_url).status_code == 204
    assert client.get(field_url).status_code == 404
    assert client.delete(farm_url).status_code == 204
    assert client.get(farm_url).status_code == 404
    assert db.scalar(select(func.count()).select_from(models.AuditLog)) >= 6


def test_null_clears_optional_values_and_zero_stays_known(client):
    url = f"{PREFIX}/farms/{FARM_ID}"
    before = client.get(url).json()
    result = client.patch(
        url, json={"district": None, "family_reserve_som": None, "cash_som": None}
    )
    assert result.status_code == 200, result.text
    farm = result.json()
    assert farm["district"] is None and farm["cash_som"] is None
    assert farm["name"] == before["name"] and farm["fields"] == before["fields"]
    assert "cash_accounts" in farm["unknown_inputs"]
    result = client.patch(url, json={"family_reserve_som": 0, "cash_som": 0})
    assert result.json()["cash_som"] == result.json()["family_reserve_som"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": None},
        {"name": "   "},
        {"family_reserve_som": 1.5},
        {"family_reserve_som": True},
        {"cash_som": 10**20},
        {"surprise": 12},
    ],
)
def test_patch_validation_is_problem_json(client, payload):
    response = client.patch(f"{PREFIX}/farms/{FARM_ID}", json=payload)
    assert response.status_code == 422, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["errors"]


def test_catalogs_and_cursor_pagination(client):
    crops = client.get(f"{PREFIX}/catalog/crops").json()
    assert len(crops) == 5 and all(c["price"]["unit"] == "t" for c in crops)
    rotations = client.get(f"{PREFIX}/catalog/rotations?zone=chuy").json()
    assert len(rotations) == 3
    assert all(r["status"] == "experimental" and r["approved_by"] is None for r in rotations)
    assert client.get(f"{PREFIX}/catalog/rotations?zone=unknown").json() == []
    assert len(client.get(f"{PREFIX}/scenarios/presets").json()) == 5
    assert client.post(f"{PREFIX}/farms", json={"name": "Другое"}).status_code == 201
    page1 = client.get(f"{PREFIX}/farms?limit=1").json()
    page2 = client.get(
        f"{PREFIX}/farms", params={"limit": 1, "cursor": page1["next_cursor"]}
    ).json()
    assert page1["items"][0]["id"] != page2["items"][0]["id"]
    assert page2["next_cursor"] is None


def test_idempotency_and_conflict(client, db):
    headers = {"Idempotency-Key": "same-request"}
    url = f"{PREFIX}/farms/{FARM_ID}/fields"
    one = client.post(url, json=point_field(), headers=headers)
    two = client.post(url, json=point_field(), headers=headers)
    assert one.status_code == two.status_code == 201, two.text
    assert one.json() == two.json()
    conflict = client.post(url, json=point_field(name="Другое"), headers=headers)
    assert conflict.status_code == 409
    assert db.scalar(select(func.count()).select_from(models.Field)) == 4


def test_cross_farm_and_unknown_foreign_keys_are_rejected(client):
    other = client.post(f"{PREFIX}/farms", json={"name": "Чужое"}).json()["id"]
    field = str(seed_id("field/asan/maize"))
    url = f"{PREFIX}/farms/{other}/fields/{field}"
    assert client.get(url).status_code == 404
    assert client.patch(url, json={"name": "Ошибка"}).status_code == 404
    assert client.delete(url).status_code == 404
    result = client.post(f"{PREFIX}/farms/{other}/fields", json=point_field(canal_id=str(uuid4())))
    assert result.status_code == 404
    assert client.get(f"{PREFIX}/farms/{other}").json()["fields"] == []


def test_geometry_calculation_overlap_and_invalid_polygon(client):
    farm = client.post(f"{PREFIX}/farms", json={"name": "Контуры"}).json()["id"]
    url = f"{PREFIX}/farms/{farm}/fields"
    geometry = load_seed().farm.fields[0].geometry.model_dump()
    response = client.post(url, json={"name": "Контур", "geometry": geometry})
    assert response.status_code == 201, response.text
    assert response.json()["area_ha"] == pytest.approx(2, rel=0.001)
    assert response.json()["location"]["type"] == "Point"
    assert client.post(url, json={"name": "Дубль", "geometry": geometry}).status_code == 422
    shape = {"type": "Polygon", "coordinates": [[[74, 42], [75, 43], [74, 43], [75, 42], [74, 42]]]}
    assert client.post(url, json={"name": "Бантик", "geometry": shape}).status_code == 422
    assert len(client.get(url).json()["features"]) == 1


def test_orchard_is_protected_and_failed_patch_is_atomic(client):
    url = f"{PREFIX}/farms/{FARM_ID}/fields/{seed_id('field/asan/orchard')}"
    before = client.get(url).json()
    assert client.delete(url).status_code == 409
    response = client.patch(
        url,
        json={
            "name": "Не сохранять",
            "season": {
                "crop_variant_id": str(seed_id("variant/maize_silage")),
                "year": 2027,
            },
        },
    )
    assert response.status_code == 422
    assert client.get(url).json() == before
    assert client.patch(url, json={"area_ha": 10}).status_code == 422


def test_demo_finance_is_not_exposed_to_avp(client):
    response = client.get(f"{PREFIX}/farms/{FARM_ID}", headers={"X-Demo-Role": "avp"})
    assert response.status_code == 403
