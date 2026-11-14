"""Сервис и API модуля воды на реальных снимках NASA POWER из data/snapshots."""

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.water import demo_data, service
from app.modules.water.inputs import ScenarioInput

client = TestClient(app)

MAIZE_FIELD = demo_data.FARM["fields"][2]
MAIZE = demo_data.CROPS["maize"]
SOWING = date(2027, 5, 1)


def season(year=2023, scenario=None, field=MAIZE_FIELD, crop=MAIZE, **kwargs):
    return service.simulate_field(field, crop, SOWING, scenario, year, **kwargs)


# ---------------------------------------------------------------- внутренние контракты


def test_history_years_are_30_full_years():
    years = service.history_years()
    assert len(years) == 30
    assert years == sorted(years) and years[-1] == 2025


def test_simulate_field_shape_and_units():
    s = season()
    assert s.year == 2023 and s.crop_code == "maize"
    assert s.sowing_date == date(2023, 5, 1)               # берутся месяц и день сева
    assert sum(d.days for d in s.decades) == s.season_days == sum(s.stage_days)
    decades = [d.decade for d in s.decades]
    assert all(1 <= k <= 36 for k in decades) and decades == sorted(decades)
    assert decades[0] == 13                                # 1–10 мая
    assert 0.0 <= s.yield_multiplier <= 1.0
    assert abs(s.balance_error_mm) <= 0.5                  # приёмка: баланс сходится

    eta_field = s.inputs["field_efficiency"].value
    for d in s.decades:
        # 1 мм на 1 га = 10 м³; брутто = нетто / η_field
        assert d.need_gross_m3 == pytest.approx(d.need_net_mm * 10 * s.area_ha / eta_field,
                                                abs=1.0)
        assert d.used_m3 <= d.received_m3 + 0.1            # поле не берёт больше поданного
        assert d.eta_mm <= d.etc_mm + 0.01
        assert d.need_head_m3 >= d.need_gross_m3           # на голове канала нужно больше
    assert s.totals.need_gross_m3 == pytest.approx(sum(d.need_gross_m3 for d in s.decades),
                                                   abs=1.0)


def test_net_is_not_gross_at_service_level():
    """До корней доходит received × η_field, а не весь поданный объём (пример 15.2)."""
    s = season()
    eta_field = s.inputs["field_efficiency"].value
    reached_roots_mm = s.totals.received_m3 * eta_field / (10 * s.area_ha)
    assert s.totals.irrigation_net_mm <= reached_roots_mm + 0.1
    assert s.totals.irrigation_net_mm < s.totals.received_m3 / (10 * s.area_ha)


def test_reproducible():
    """Одинаковые входы -> одинаковый результат, в том числе без кэша."""
    first = season().model_dump()
    service._simulate.cache_clear()
    assert season().model_dump() == first


def test_provenance_and_completeness():
    s = season()
    assert s.snapshots and s.snapshots[0].startswith("power_ag_")
    assert s.model_version and s.et0_method == "penman_monteith"
    assert s.completeness == "partial" and "canal_efficiency" in s.unknown_inputs
    assert s.inputs["field_efficiency"].source_type == "reference"
    assert s.inputs["field_efficiency"].range == (0.45, 0.60)
    assert s.yield_status == "model_estimate"
    assert s.yield_t_ha == round(s.yield_t_ha, 1)          # не точнее 0,1 т/га


def test_unknown_water_limit_is_flagged_not_zero():
    """Пропуск ≠ ноль: без данных об очереди берётся справочная норма с пометкой."""
    field = {**MAIZE_FIELD, "water": None}
    s = season(field=field)
    assert "water_limit" in s.unknown_inputs and "water_reliability" in s.unknown_inputs
    assert s.completeness == "partial"
    assert s.totals.received_m3 > 0
    assert s.inputs["turn_volume_m3"].source_type == "unknown"


def test_unknown_soil_is_flagged():
    field = {**MAIZE_FIELD, "soil_type": "unknown"}
    s = season(field=field)
    assert "taw" in s.unknown_inputs
    assert s.inputs["taw_mm_per_m"].source_type == "unknown"


def test_rainfed_field_receives_no_water():
    s = season(field={**MAIZE_FIELD, "irrigation_method": "none"})
    assert s.totals.received_m3 == 0 and s.totals.irrigation_net_mm == 0
    assert s.yield_multiplier < season().yield_multiplier


@pytest.mark.parametrize("crop_code", ["maize", "alfalfa", "apple"])
def test_less_supply_never_raises_yield_any_year(crop_code):
    """Монотонность на реальных данных: меньше подача — урожай не растёт."""
    crop = demo_data.CROPS[crop_code]
    field = {**MAIZE_FIELD, "id": f"mono-{crop_code}"}
    for year in service.history_years():
        full = season(year, None, field, crop)
        half = season(year, ScenarioInput(water_supply_factor=0.5), field, crop)
        assert half.yield_multiplier <= full.yield_multiplier + 1e-9
        assert half.totals.received_m3 <= full.totals.received_m3


def test_scenario_effects():
    base = season()
    hot = season(scenario={"temp_delta_c": 3.0})
    assert hot.totals.etc_mm > base.totals.etc_mm          # теплее — потребность выше
    dry = season(scenario={"precip_factor": 0.5})
    assert dry.totals.precip_mm == pytest.approx(base.totals.precip_mm * 0.5, rel=0.01)
    july_only = season(scenario={"water_supply_factor": 0.8, "water_supply_months": [7, 8]})
    assert july_only.totals.received_m3 < base.totals.received_m3
    shifted = season(scenario={"supply_shift_days": 30})
    assert [d.turns_planned for d in shifted.decades] != [d.turns_planned
                                                          for d in base.decades]


def test_scenario_year_is_used_when_year_omitted():
    s = service.simulate_field(MAIZE_FIELD, MAIZE, SOWING,
                               {"climate_mode": "historical_year",
                                "climate_params": {"year": 2023}})
    assert s.year == 2023


def test_gdd_stages_shorten_in_warmer_scenario():
    crop = {**MAIZE, "code": "maize-gdd", "gdd_required": 1500.0}
    base = season(crop=crop)
    hot = season(crop=crop, scenario={"temp_delta_c": 3.0})
    assert hot.season_days < base.season_days


def test_accepts_plain_objects_with_tz_attribute_names():
    """Чужие объекты читаются по именам атрибутов из раздела 7.1 ТЗ (не только dict)."""
    field = SimpleNamespace(id="obj-1", name="Объект", area_ha=1.5, lat=42.86, lon=74.30,
                            elevation_m=740.0, soil_type="loam", irrigation_method="drip",
                            turn_interval_days=7, turn_hours=6.0, flow_l_s=20.0)
    crop = SimpleNamespace(code="maize", name_ru="Кукуруза", kc_ini=0.3, kc_mid=1.2,
                           kc_end=0.6, stage_days=[30, 40, 50, 30], root_depth_m=1.2,
                           p_depletion=0.55, ky=1.25, t_base=10.0)
    s = service.simulate_field(field, crop, date(2027, 5, 1), None, 2020)
    assert s.field_id == "obj-1" and s.area_ha == 1.5
    assert s.inputs["field_efficiency"].range == (0.85, 0.95)   # капельный
    assert s.inputs["turn_interval_days"].value == 7


def test_year_outside_snapshot_is_rejected():
    with pytest.raises(ValueError):
        season(1900)


def test_daily_series_on_request():
    s = season(daily=True)
    assert s.daily is not None and len(s.daily.dates) == s.season_days
    assert len(s.daily.dr) == len(s.daily.raw) == s.season_days
    assert season().daily is None


def test_stress_test_is_fast_enough():
    """NFR-2: пересчёт хозяйства (3 поля × 30 лет) в новом сценарии — заметно быстрее 2 с."""
    import time

    scenario = ScenarioInput(water_supply_factor=0.77, temp_delta_c=1.3)
    started = time.perf_counter()
    for field in demo_data.FARM["fields"]:
        crop = demo_data.CROPS[field["crop_code"]]
        for year in service.history_years():
            service.simulate_field(field, crop, crop["default_sowing"], scenario, year)
    assert time.perf_counter() - started < 2.0


# ---------------------------------------------------------------- API


def test_api_water_balance():
    r = client.get("/api/v1/fields/asan-maize/water-balance")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["field"]["source"] == "demo" and body["field"]["crop_code"] == "maize"
    assert body["year_mode"] == "median" and body["year"] in body["ensemble"]["years"]
    assert len(body["ensemble"]["years"]) == 30
    y = body["ensemble"]["yield_multiplier"]
    assert y["p10"] <= y["p50"] <= y["p90"]
    assert body["cell"]["resolution_note_key"] == "climate.resolution_note"
    first = body["season"]["decades"][0]
    assert {"decade", "need_net_mm", "need_gross_m3", "received_m3", "deficit_m3",
            "deficit_pct", "ks_avg", "status"} <= first.keys()
    assert body["season"]["daily"] is None


def test_api_water_balance_year_and_daily():
    r = client.get("/api/v1/fields/asan-maize/water-balance", params={"year": 2023,
                                                                      "daily": "true"})
    body = r.json()
    assert r.status_code == 200 and body["year"] == 2023 and body["year_mode"] == "requested"
    assert len(body["season"]["daily"]["dates"]) == body["season"]["season_days"]


def test_api_errors_are_problem_json():
    r = client.get("/api/v1/fields/no-such-field/water-balance")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    assert client.get("/api/v1/fields/asan-maize/water-balance",
                      params={"year": 1900}).status_code == 422
    assert client.get("/api/v1/fields/asan-maize/water-balance",
                      params={"scenario": "no-such"}).status_code == 404
    assert client.get("/api/v1/fields/asan-maize/climate",
                      params={"from": "2024-05-01", "to": "2024-04-01"}).status_code == 422


def test_api_climate():
    r = client.get("/api/v1/fields/asan-maize/climate")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["days"]) == 365 and body["date_from"] == "2025-01-01"
    assert len(body["decade_norms"]) == 36 and len(body["history_years"]) == 30
    assert body["et0_method"] == "penman_monteith"
    assert "NASA" in body["attribution"]
    july = [d["et0"] for d in body["days"] if d["date"][5:7] == "07"]
    assert 4.0 < sum(july) / len(july) < 12.0              # правдоподобный июльский ET0

    r = client.get("/api/v1/fields/asan-maize/climate",
                   params={"from": "2023-07-01", "to": "2023-07-10"})
    assert [d["date"] for d in r.json()["days"]][0] == "2023-07-01"
    assert len(r.json()["days"]) == 10


def test_api_data_sources():
    r = client.get("/api/v1/data-sources")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "NASA Langley Research Center (LaRC) POWER Project" in body["attribution"]
    assert body["offline_ready"] is True
    power = body["datasets"][0]
    assert power["id"] == "nasa_power_daily_ag" and power["status"] == "active"
    assert {s["point_name"] for s in power["snapshots"]} == {"Сокулук", "Кант", "Кара-Балта"}
    for snapshot in power["snapshots"]:
        assert snapshot["period_start"] == "1995-01-01" and len(snapshot["sha256"]) == 64
        assert len(snapshot["cell"]["bbox"]) == 4
    # активным помечено только то, что реально участвует в расчёте
    assert [d["id"] for d in body["datasets"] if d["status"] == "active"] == [
        "nasa_power_daily_ag"]
    assert client.get("/api/v1/data-sources", params={"lang": "en"}).json()["datasets"][0][
        "frequency"] == "daily, since 1981"
