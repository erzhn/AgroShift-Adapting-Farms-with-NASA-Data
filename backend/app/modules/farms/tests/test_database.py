"""Real PostgreSQL/PostGIS tests, isolated in a rolled-back temporary schema.

Enable explicitly: AGROSHIFT_TEST_DB=1 pytest -m db. No existing tables are cleared.
"""

import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.core.errors import NotFoundError
from app.db.base import Base
from app.modules.farms.demo import FARM_ID, load_seed, seed_id
from app.modules.farms.seed import seed_farms
from app.modules.farms.service import get_crop, get_farm, list_scenario_presets

pytestmark = pytest.mark.db


@pytest.fixture
def db():
    if os.getenv("AGROSHIFT_TEST_DB") != "1":
        pytest.skip("Set AGROSHIFT_TEST_DB=1 to run isolated PostGIS integration tests")
    from app.db.session import engine

    with engine.connect() as conn:
        transaction = conn.begin()
        schema = "farms_test_" + uuid4().hex
        try:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            # Use explicit schema translation so public tables cannot be mistaken for test tables.
            scoped = conn.execution_options(schema_translate_map={None: schema})
            Base.metadata.create_all(scoped)
            with Session(bind=scoped, join_transaction_mode="create_savepoint") as session:
                yield session
        finally:
            transaction.rollback()  # Includes all DDL and rows, even when a test fails.


def test_seed_round_trip_and_detached_contracts(db):
    counts = seed_farms(db)
    assert counts["crops"] == 5
    assert counts["fields"] == 3
    assert counts["scenarios"] == 5
    farm = get_farm(str(FARM_ID), session=db)
    crop = get_crop(seed_id("crop/maize"), session=db)
    db.expunge_all()
    assert farm.area_ha == 6
    assert farm.cash_som == 150000
    assert farm.herds[0].head_count == 8
    assert farm.water_rights[0].turn_hours == 8
    assert all(field.geometry.type == "Polygon" for field in farm.fields)
    assert {season.crop_id for field in farm.fields for season in field.seasons} == {
        seed_id("crop/apple"),
        seed_id("crop/alfalfa"),
        seed_id("crop/maize"),
    }
    assert crop.variants[0].yield_potential_t_ha == 35
    assert sum(cost.cost_som_ha for cost in crop.variants[0].costs) == 72000
    assert json.loads(crop.model_dump_json())["provenance"]["ky"]["source_type"] == "reference"


def test_repeat_seed_preserves_edits_and_does_not_duplicate(db):
    seed_farms(db)
    db.execute(
        update(models.Farm)
        .where(models.Farm.id == FARM_ID)
        .values(name="Исправлено фермером", family_reserve_som=12345)
    )
    db.execute(update(models.PriceItem).values(price_som=123))
    assert all(count == 0 for count in seed_farms(db).values())
    farm = get_farm(FARM_ID, session=db)
    assert farm.name == "Исправлено фермером"
    assert farm.family_reserve_som == 12345
    assert get_crop(seed_id("crop/maize"), session=db).price.price_som == 123
    assert db.scalar(select(func.count()).select_from(models.Field)) == 3
    assert db.scalar(select(func.count()).select_from(models.CostNorm)) == 19


def test_postgis_geometry_is_valid_two_hectares_without_overlap(db):
    seed_farms(db)
    rows = db.execute(
        text(
            "SELECT id, area_ha, ST_IsValid(geometry), ST_SRID(geometry), "
            "ST_Area(geometry::geography)/10000, ST_Covers(geometry, location) FROM fields"
        )
    ).all()
    assert len(rows) == 3
    for _, area, valid, srid, geodesic_area, covers in rows:
        assert valid and covers
        assert srid == 4326
        assert geodesic_area == pytest.approx(area, rel=0.001)
    assert (
        db.scalar(
            text(
                "SELECT count(*) FROM fields a JOIN fields b ON a.id < b.id "
                "WHERE ST_Intersects(a.geometry, b.geometry)"
            )
        )
        == 0
    )


def test_missing_price_and_cash_stay_unknown(db):
    seed_farms(db)
    db.execute(models.PriceItem.__table__.delete())
    db.execute(models.CashAccount.__table__.delete())
    crop = get_crop(seed_id("crop/maize"), session=db)
    farm = get_farm(FARM_ID, session=db)
    assert crop.price is None and "price" in crop.unknown_inputs
    assert farm.cash_som is None and "cash_accounts" in farm.unknown_inputs
    assert crop.completeness == farm.completeness == "partial"


@pytest.mark.parametrize("read", [get_farm, get_crop])
@pytest.mark.parametrize("entity_id", [uuid4(), "invalid-uuid"])
def test_missing_ids_have_domain_not_found_error(db, read, entity_id):
    with pytest.raises(NotFoundError) as error:
        read(entity_id, session=db)
    assert error.value.status == 404


def test_preset_round_trip_preserves_month_scope(db):
    seed_farms(db)
    presets = {s.preset_code: s for s in list_scenario_presets(session=db)}
    assert len(presets) == 5
    assert presets["water_minus_20"].water_supply_months == [7, 8]
    assert presets["like_2023"].climate_params.year == 2023
    assert presets["feed_plus_40"].price_factors == {"feed": 1.4}
    assert presets["payment_plus_60"].payment_delay_days == 60


def test_late_unique_conflict_rolls_back_entire_seed(db):
    # Conflict at the last batch ensures farm, crops and cost rows also roll back.
    existing = models.Scenario(
        id=uuid4(),
        name="Сценарий пользователя",
        preset_code="payment_plus_60",
        climate_mode="historical_year",
        climate_params={"year": 2023},
    )
    db.add(existing)
    db.flush()
    with pytest.raises(IntegrityError):
        seed_farms(db)
    assert db.scalar(select(func.count()).select_from(models.Farm)) == 0
    assert db.scalar(select(func.count()).select_from(models.Crop)) == 0
    assert db.scalar(select(func.count()).select_from(models.Scenario)) == 1


def test_seed_uses_callers_transaction(db):
    seed_farms(db)
    assert get_farm(FARM_ID, session=db).name == "Асан"
    db.rollback()
    assert db.scalar(select(func.count()).select_from(models.Farm)) == 0


def test_price_selection_ignores_private_and_wrong_unit_prices(db):
    seed_farms(db)
    base = load_seed().crops[1].price.model_dump()
    db.add_all(
        [
            models.PriceItem(**dict(base, id=uuid4(), item_kind="crop", unit="kg", price_som=99)),
            models.PriceItem(
                **dict(base, id=uuid4(), item_kind="crop", farm_id=FARM_ID, price_som=999)
            ),
            models.PriceItem(
                **dict(base, id=uuid4(), item_kind="crop", region="osh", price_som=9999)
            ),
        ]
    )
    db.flush()
    assert get_crop(seed_id("crop/maize"), session=db).price.price_som == 4000
