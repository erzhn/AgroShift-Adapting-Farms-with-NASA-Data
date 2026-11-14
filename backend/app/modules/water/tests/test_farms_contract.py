"""Стык с модулем farms: simulate_field принимает его объекты как есть.

Берётся офлайн-сид модуля farms (без базы). Если модуль farms изменит форму объектов,
эти тесты упадут раньше, чем сломается демо.
"""

import pytest

from app.modules.water import service, sources
from app.modules.water.inputs import CropInput, FieldInput, ScenarioInput, WaterInput

demo = pytest.importorskip("app.modules.farms.demo")


@pytest.fixture(scope="module")
def bundle():
    return demo.load_seed()


def _plan(bundle, field):
    """Культура и срок сева поля — как их отдаёт farms: через основной сезон."""
    season = max((s for s in field.seasons if s.is_main), key=lambda s: s.year)
    crop = next(c for c in bundle.crops if c.id == season.crop_id)
    return crop, season.sowing_date


def test_field_and_crop_objects_are_understood(bundle):
    farm = bundle.farm
    field = farm.fields[0]
    crop, _ = _plan(bundle, field)

    field_in = FieldInput.from_any(field)
    assert field_in.id == str(field.id) and field_in.area_ha == field.area_ha
    assert field_in.lat == pytest.approx(42.86, abs=0.2)      # центр контура (Polygon)
    assert field_in.lon == pytest.approx(74.3, abs=0.3)
    assert field_in.irrigation_method == field.irrigation_method.value

    crop_in = CropInput.from_any(crop)
    assert crop_in.code == crop.code and crop_in.stage_days == tuple(crop.stage_days)
    assert crop_in.is_perennial == crop.is_perennial
    assert crop_in.yield_potential_t_ha == crop.variants[0].yield_potential_t_ha


def test_water_right_of_the_farm_is_shared_by_area(bundle):
    farm = bundle.farm
    right = farm.water_rights[0]
    total = sum(f.area_ha for f in farm.fields if f.irrigation_method.value != "none")
    for field in farm.fields:
        water = WaterInput.from_any(sources._water_from_farm(farm, field))
        assert water.turn_interval_days == right.turn_interval_days
        assert water.turn_hours == right.turn_hours and water.flow_l_s == right.flow_l_s
        assert water.share == pytest.approx(field.area_ha / total)
        assert water.failure_months == tuple(right.failure_months or ())


def test_seasonal_limit_hours_are_not_hours_per_turn():
    """limit_hours в WaterRight — сезонное право, а не часы одной очереди."""
    water = WaterInput.from_any({"turn_interval_days": 8, "limit_hours": 100.0,
                                 "flow_l_s": 60.0})
    assert water.turn_hours is None
    assert water.limit_m3 == pytest.approx(100 * 3600 * 60 / 1000)


def test_simulate_field_with_farms_objects(bundle):
    farm = bundle.farm
    for field in farm.fields:
        crop, sowing = _plan(bundle, field)
        season = service.simulate_field(field, crop, sowing, None, 2020,
                                        water=sources._water_from_farm(farm, field))
        assert season.field_id == str(field.id) and season.crop_code == crop.code
        assert 0.0 <= season.yield_multiplier <= 1.0
        assert abs(season.balance_error_mm) <= 0.5
        assert "water_limit" not in season.unknown_inputs     # очередь взята из прав
        assert season.totals.received_m3 > 0
        for d in season.decades:
            # поле, которое читает модуль стратегий: потребность брутто слоем на 1 га
            assert d.gross_mm == pytest.approx(d.need_gross_m3 / (10 * field.area_ha),
                                               abs=0.06)


def test_scenario_presets_are_understood(bundle):
    by_code = {s.preset_code: s for s in bundle.scenarios}
    like_2023 = ScenarioInput.from_any(by_code["like_2023"])
    assert like_2023.climate_year == 2023

    minus_20 = by_code["water_minus_20"]
    parsed = ScenarioInput.from_any(minus_20)
    assert parsed.water_supply_factor == minus_20.water_supply_factor
    assert parsed.water_supply_months == tuple(minus_20.water_supply_months or ())

    farm = bundle.farm
    field = farm.fields[0]
    crop, sowing = _plan(bundle, field)
    water = sources._water_from_farm(farm, field)
    base = service.simulate_field(field, crop, sowing, None, 2020, water=water)
    less = service.simulate_field(field, crop, sowing, minus_20, 2020, water=water)
    assert less.totals.received_m3 < base.totals.received_m3
    assert less.yield_multiplier <= base.yield_multiplier + 1e-9


def test_strategies_style_scenario_object():
    """Модуль стратегий передаёт свой объект сценария: месяцы — в поле water_months."""

    class Scn:
        water_supply_factor = 0.8
        supply_shift_days = 10.0
        temp_delta_c = 1.5
        precip_factor = 0.9
        water_months = (7, 8)

    parsed = ScenarioInput.from_any(Scn())
    assert parsed.water_supply_months == (7, 8)
    assert parsed.supply_shift_days == 10 and parsed.temp_delta_c == 1.5


def test_incomplete_crop_is_rejected_with_a_clear_message():
    """Культура без глубины корней — не «ноль» и не тихая подстановка: явная ошибка."""
    with pytest.raises(ValueError, match="root_depth_m"):
        CropInput.from_any({"code": "x", "kc": (0.4, 1.0, 0.6), "stage_days": (25, 35, 40, 30),
                            "ky": 1.0})
