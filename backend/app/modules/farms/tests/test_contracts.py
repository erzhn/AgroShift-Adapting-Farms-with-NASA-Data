"""Contract and unit tests run offline, without a PostgreSQL server."""

import json
import math
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.farms.demo import FARM_ID, load_seed, seed_id
from app.modules.farms.schemas import Crop, Farm, Field, Polygon, Scenario


@pytest.fixture
def bundle():
    return load_seed()


def test_reproducible_offline_bundle(bundle):
    assert bundle.model_dump_json() == load_seed().model_dump_json()
    assert bundle.farm.id == FARM_ID
    assert {c.code for c in bundle.crops} == {"alfalfa", "maize", "wheat", "beans", "apple"}
    assert len({c.id for c in bundle.crops}) == 5


def test_asan_areas_assets_and_irrigation(bundle):
    farm = bundle.farm
    assert len(farm.fields) == 3
    assert [field.area_ha for field in farm.fields] == [2, 2, 2]
    assert farm.area_ha == 6  # Orchard must not be added for a second time.
    assert len(farm.orchards) == 1
    assert farm.orchards[0].field_id in {f.id for f in farm.fields}
    assert farm.herds[0].head_count == 8
    assert farm.herds[0].species == "cow"
    right = farm.water_rights[0]
    assert 7 <= right.turn_interval_days <= 10
    assert right.turn_hours == 16
    assert right.limit_hours is None  # Seasonal entitlement is not duration of a turn.
    assert right.flow_l_s * 3.6 * right.turn_hours == 3456
    assert right.failure_months == [8]
    assert farm.cash_som == 150000
    assert farm.family_reserve_som == 10000
    assert not any([farm.consent_agronomist, farm.consent_canal_plan, farm.consent_analytics])


def test_all_field_seasons_reference_existing_crop_variants(bundle):
    crops = {crop.id: crop for crop in bundle.crops}
    for field in bundle.farm.fields:
        assert len(field.seasons) == 1
        season = field.seasons[0]
        variant = crops[season.crop_id].variants[0]
        assert season.crop_variant_id == variant.id
        assert season.planned_yield_t_ha == variant.yield_potential_t_ha
        assert (season.harvest_date - season.sowing_date).days + 1 == sum(
            crops[season.crop_id].stage_days
        )
    maize = next(c for c in bundle.crops if c.code == "maize")
    assert maize.variants[0].product == "silage"
    assert maize.variants[0].yield_potential_t_ha == 35
    assert maize.price.price_som == 4000
    assert maize.price.unit == "t"


@pytest.mark.parametrize(
    "code,expected",
    [
        ("alfalfa", (0.4, 0.95, 0.9, 0.55, 1.1)),
        ("maize", (0.3, 1.2, 0.6, 0.55, 1.25)),
        ("wheat", (0.3, 1.15, 0.25, 0.55, 1.15)),
        ("beans", (0.4, 1.15, 0.35, 0.45, 1.15)),
        ("apple", (0.45, 0.95, 0.7, 0.5, 1.0)),
    ],
)
def test_reference_coefficients_and_honest_apple_ky(bundle, code, expected):
    crop = next(c for c in bundle.crops if c.code == code)
    assert (crop.kc_ini, crop.kc_mid, crop.kc_end, crop.p_depletion, crop.ky) == expected
    assert crop.provenance["kc_mid"].citation.startswith("https://www.fao.org/")
    assert crop.provenance["ky"].source_type == (
        "user_estimate" if code == "apple" else "reference"
    )
    assert crop.ky_stages is None
    assert "ky_stages" in crop.unknown_inputs


def test_every_seed_crop_numeric_input_has_provenance(bundle):
    for crop in bundle.crops:
        for name in (
            "kc_ini",
            "kc_mid",
            "kc_end",
            "stage_days",
            "height_m",
            "root_depth_m",
            "p_depletion",
            "ky",
            "t_base",
            "ky_stages",
            "gdd_required",
            "t_min_kill",
            "t_crit_heat",
            "k_heat",
            "water_critical_stages",
        ):
            source = crop.provenance[name]
            assert source.note
            if getattr(crop, name) is None:
                assert source.source_type == "unknown"
                assert source.confidence == 0
            elif source.source_type == "reference":
                assert source.citation
        assert crop.price.source_type == "user_estimate"
        for variant in crop.variants:
            assert variant.provenance["yield_potential_t_ha"].source_type == "user_estimate"
            for cost in variant.costs:
                assert {"month", "cost_som_ha", "labour_h_ha"} <= cost.provenance.keys()


def test_no_fabricated_zero_for_missing_inputs(bundle):
    farm_data = bundle.farm.model_dump(round_trip=True)
    farm_data.update(cash_accounts=[], family_reserve_som=None, water_rights=[])
    farm = Farm.model_validate(farm_data)
    assert farm.cash_som is None
    assert farm.family_reserve_som is None
    assert farm.completeness == "partial"
    assert {"cash_accounts", "family_reserve_som", "water_rights"} <= set(farm.unknown_inputs)
    crop_data = bundle.crops[0].model_dump(round_trip=True)
    crop_data.update(price=None)
    crop = Crop.model_validate(crop_data)
    assert crop.price is None
    assert crop.completeness == "partial"
    assert "price" in crop.unknown_inputs


@pytest.mark.parametrize("invalid", [-1, 1.5, "10000", True, math.inf])
def test_money_requires_whole_som(bundle, invalid):
    values = bundle.farm.model_dump(round_trip=True)
    values["family_reserve_som"] = invalid
    with pytest.raises(ValidationError):
        Farm.model_validate(values)


@pytest.mark.parametrize(
    "name,value",
    [
        ("stage_days", [10, 20, 30]),
        ("stage_days", [10, 0, 30, 40]),
        ("stage_days", [10, 2.5, 30, 40]),
        ("root_depth_m", 0),
        ("p_depletion", 1),
        ("p_depletion", -0.1),
        ("kc_mid", math.nan),
        ("ky", math.inf),
        ("ky_stages", [0.5, 1, 1.5]),
        ("water_critical_stages", [0]),
    ],
)
def test_crop_rejects_invalid_inputs(bundle, name, value):
    values = bundle.crops[0].model_dump(round_trip=True)
    values[name] = value
    with pytest.raises(ValidationError):
        Crop.model_validate(values)


@pytest.mark.parametrize(
    "ring",
    [
        [[0, 0], [1, 0], [1, 1]],
        [[0, 0], [1, 0], [1, 1], [0, 1]],
        [[0, 0], [0, 0], [0, 0], [0, 0]],
        [[181, 0], [1, 0], [1, 1], [181, 0]],
    ],
)
def test_invalid_geojson_rings(ring):
    with pytest.raises(ValidationError):
        Polygon(coordinates=[ring])


def test_no_two_main_crops_or_cross_farm_assets(bundle):
    values = bundle.farm.fields[0].model_dump(round_trip=True)
    values["seasons"].append(dict(values["seasons"][0], id=uuid4()))
    with pytest.raises(ValidationError, match="одна основная"):
        Field.model_validate(values)
    values = bundle.farm.model_dump(round_trip=True)
    values["herds"][0]["farm_id"] = uuid4()
    with pytest.raises(ValidationError, match="другому хозяйству"):
        Farm.model_validate(values)


def test_five_distinct_presets_with_scoped_effects(bundle):
    presets = {s.preset_code: s for s in bundle.scenarios}
    assert len(presets) == 5
    historical = presets["like_2023"]
    assert historical.climate_params.year == 2023
    assert historical.temp_delta_c == 0  # Do not double-count heat already in the NASA year.
    assert presets["water_minus_20"].water_supply_factor == 0.8
    assert presets["water_minus_20"].water_supply_months == [7, 8]
    assert presets["feed_plus_40"].price_factors == {"feed": 1.4}
    assert presets["payment_plus_60"].payment_delay_days == 60
    for scenario in presets.values():
        assert scenario.farm_id is None
        assert {
            "water_supply_factor",
            "price_factors",
            "climate_params",
            "payment_delay_days",
        } <= scenario.provenance.keys()


@pytest.mark.parametrize(
    "name,value",
    [
        ("water_supply_factor", 0.49),
        ("water_supply_factor", 1.21),
        ("water_supply_months", []),
        ("water_supply_months", [7, 7]),
        ("water_supply_months", [13]),
        ("supply_shift_days", 31),
        ("temp_delta_c", -1),
        ("temp_delta_c", 3.1),
        ("precip_factor", 0.49),
        ("price_factors", {"feed": 1.51}),
        ("payment_delay_days", 121),
        ("yield_factor", 0.69),
        ("climate_params", {}),
        ("climate_params", {"year": 2023, "percentile": 50}),
    ],
)
def test_scenario_bounds(bundle, name, value):
    values = bundle.scenarios[0].model_dump(round_trip=True)
    values[name] = value
    with pytest.raises(ValidationError):
        Scenario.model_validate(values)


def test_serialization_preserves_units_ids_and_sources(bundle):
    serialized = json.loads(bundle.model_dump_json())
    assert serialized["farm"]["id"] == str(FARM_ID)
    assert serialized["farm"]["cash_accounts"][0]["as_of"] == "2027-01-01"
    assert isinstance(serialized["farm"]["cash_som"], int)
    assert serialized["crops"][0]["price"]["unit"] == "t"
    assert serialized["crops"][0]["id"] == str(seed_id("crop/alfalfa"))
