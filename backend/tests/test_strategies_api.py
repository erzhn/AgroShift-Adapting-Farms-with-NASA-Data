"""API модуля «Стратегии и деньги»: генерация, деньги, стресс-тест, точки поломки."""

import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services import strategies as service

client = TestClient(app)
API = "/api/v1"
PCT = ("p10", "p50", "p90")


@pytest.fixture(autouse=True)
def clean_store(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "runs_dir", tmp_path)
    service._records.clear()
    service._engines.clear()


def generate(**body) -> dict:
    r = client.post(f"{API}/farms/demo/strategies:generate", json=body or None)
    assert r.status_code == 200, r.text
    return r.json()


def strategy(gen: dict, kind: str) -> dict:
    return next(s for s in gen["strategies"] if kind in s["types"])


def test_generate_returns_strategies_and_my_plan():
    gen = generate()
    kinds = [k for s in gen["strategies"] for k in s["types"]]
    assert sorted(kinds) == ["income", "resilient", "user", "water_light"]
    assert 1 < gen["schemes_checked"] <= 500
    assert gen["provenance"]["n_samples"] == 30 == len(gen["provenance"]["years"])
    for s in gen["strategies"]:
        m = s["metrics"]
        assert m["income_som"]["p10"] <= m["income_som"]["p50"] <= m["income_som"]["p90"]
        assert all(isinstance(m["income_som"][p], int) for p in PCT)  # деньги — целые сомы
        assert 0 <= m["cash_gap"]["probability"] <= 1
        assert s["summary_ru"] and s["summary_en"]
    assert strategy(gen, "user")["summary_ru"] == "Текущий план без изменений"
    # оптимизированные стратегии держат резерв семьи, текущий план — нет
    assert strategy(gen, "income")["metrics"]["cash_gap"]["probability"] <= 0.10
    assert strategy(gen, "resilient")["metrics"]["cash_gap"]["probability"] <= 0.05
    assert "cash_gap_risk" in strategy(gen, "user")["flags"]


def test_goals_are_respected():
    gen = generate()
    income, resilient = strategy(gen, "income"), strategy(gen, "resilient")
    water = strategy(gen, "water_light")
    assert resilient["metrics"]["cvar10_som"] >= 0
    assert water["metrics"]["peak_water_m3"] <= income["metrics"]["peak_water_m3"]
    assert water["metrics"]["peak_water_m3"] <= resilient["metrics"]["peak_water_m3"]


def test_reproducible_same_seed_same_hash():
    first = generate(seed=7)
    service._records.clear()
    service._engines.clear()
    for path in get_settings().runs_dir.glob("*.json"):
        path.unlink()
    second = generate(seed=7)
    assert first["result_hash"] == second["result_hash"]
    assert first == second
    assert generate(seed=8)["result_hash"] != first["result_hash"]


def test_runs_survive_restart():
    gen = generate()
    service._records.clear()
    service._engines.clear()
    run_id = strategy(gen, "user")["run_id"]
    assert client.get(f"{API}/runs/{run_id}/cashflow").status_code == 200


def test_get_strategy():
    gen = generate()
    for s in gen["strategies"]:
        r = client.get(f"{API}/strategies/{s['id']}")
        assert r.status_code == 200
        assert r.json() == s


def test_unknown_ids_return_problem_json():
    for url in ("/strategies/s_0000000000_user", "/runs/nope/cashflow", "/runs/r_../breakpoints"):
        r = client.get(API + url)
        assert r.status_code == 404
        assert r.headers["content-type"].startswith("application/problem+json")
    assert client.post(f"{API}/runs/r_0000000000_user/stress", json={}).status_code == 404


def test_cashflow_by_month_with_gap_marker():
    gen = generate()
    cf = client.get(f"{API}/runs/{strategy(gen, 'user')['run_id']}/cashflow").json()
    assert [m["month"] for m in cf["months"]] == list(range(1, 13))
    for m in cf["months"]:
        assert m["cash"]["p10"] <= m["cash"]["p50"] <= m["cash"]["p90"]
    # остаток сходится: Cash_m = Cash_{m-1} + поступления − расходы (по средним)
    assert cf["gap"]["first_month"] == 10  # у текущего плана деньги кончаются в октябре
    october = cf["months"][9]
    assert october["cash"]["p50"] < cf["reserve_som"]
    assert october["components"]["feed_purchase"] < 0
    assert cf["gap"]["financing_needed_som"] == cf["reserve_som"] - october["cash"]["p50"]
    ok = client.get(f"{API}/runs/{strategy(gen, 'resilient')['run_id']}/cashflow").json()
    assert ok["gap"]["first_month"] is None


def test_stress_original_breaks_fixed_holds_within_two_seconds():
    gen = generate()
    run_id = strategy(gen, "user")["run_id"]
    body = {"water_supply_factor": 0.8, "feed_price_factor": 1.4}
    started = time.perf_counter()
    r = client.post(f"{API}/runs/{run_id}/stress", json=body)
    assert time.perf_counter() - started < 2.0
    assert r.status_code == 200, r.text
    st = r.json()
    a, b, c = st["baseline"], st["stressed"], st["fixed"]
    assert b["income_som"]["p50"] < a["income_som"]["p50"]
    assert st["damage_som"] == a["income_som"]["p50"] - b["income_som"]["p50"]
    assert st["fix_needed"] and st["fix_found"]
    assert b["cash_gap"]["first_month"] is not None  # исходный план ломается
    assert c["cash_gap"]["first_month"] is None  # исправленный выдерживает
    assert st["adaptation_gain_som"] == c["income_som"]["p50"] - b["income_som"]["p50"]
    assert st["answers"]["fix_summary_ru"]
    assert st["answers"]["water_decade"]["decade"] in range(1, 37)
    assert st["answers"]["vulnerable_field"]["yield_loss"] > 0
    assert st["answers"]["feed_extra_purchase_som"] > 0  # корм подорожал на 40%


def test_stress_at_base_conditions_changes_nothing():
    gen = generate()
    st = client.post(f"{API}/runs/{strategy(gen, 'resilient')['run_id']}/stress", json={}).json()
    assert st["damage_som"] == 0
    assert st["baseline"]["cash_p50"] == st["stressed"]["cash_p50"]
    assert not st["fix_needed"]


def test_less_water_never_raises_income_or_lowers_losses():
    gen = generate()
    run_id = strategy(gen, "income")["run_id"]
    incomes, losses = [], []
    for factor in (1.0, 0.9, 0.8, 0.7, 0.6):
        body = {"water_supply_factor": factor, "with_fix": False}
        st = client.post(f"{API}/runs/{run_id}/stress", json=body).json()
        incomes.append(st["stressed"]["income_som"]["p50"])
        losses.append(max(f["yield_loss"] for f in st["stressed"]["field_losses"]))
        assert st["fixed"] is None
    assert incomes == sorted(incomes, reverse=True)
    assert losses == sorted(losses)


def test_stress_validates_slider_range():
    gen = generate()
    r = client.post(f"{API}/runs/{gen['strategies'][0]['run_id']}/stress",
                    json={"water_supply_factor": 0.1})
    assert r.status_code == 422


def test_breakpoints_sorted_with_historical_frequency():
    gen = generate()
    run_id = strategy(gen, "income")["run_id"]
    bp = client.get(f"{API}/runs/{run_id}/breakpoints").json()
    assert bp["base_violation"] is None
    points = bp["breakpoints"]
    assert points
    margins = [p["safety_margin_sigma"] for p in points]
    assert margins == sorted(margins)
    water = next(p for p in points if p["factor"] == "water_supply_factor")
    assert water["delta"] < 0 and water["unit"] == "percent"
    assert water["historical_frequency"]["of"] == 30
    assert 0 <= water["historical_frequency"]["count"] <= 30
    # порог действительно ломает план, а условия чуть мягче — ещё нет
    for factor in (water["threshold_value"], water["threshold_value"] + 0.02):
        st = client.post(f"{API}/runs/{run_id}/stress",
                         json={"water_supply_factor": factor, "with_fix": False}).json()
        broke = (
            st["stressed"]["cash_gap"]["first_month"] is not None
            or max(f["yield_loss"] for f in st["stressed"]["field_losses"])
            > bp["yield_loss_limit"]
        )
        assert broke == (factor == water["threshold_value"])
    assert client.get(f"{API}/runs/{run_id}/breakpoints").json() == bp  # из кэша — то же


def test_breakpoints_of_broken_plan_report_base_violation():
    gen = generate()
    bp = client.get(f"{API}/runs/{strategy(gen, 'user')['run_id']}/breakpoints").json()
    assert bp["base_violation"] == {
        "violated_constraint": "cash_gap", "month": 10, "field_id": None, "field_name": None,
    }
    assert bp["breakpoints"] == []


def test_run_summary_contract_for_ai():
    gen = generate()
    run_id = strategy(gen, "income")["run_id"]
    summary = service.get_run_summary(run_id)
    assert summary.run_id == run_id and summary.breakpoints is None
    assert summary.metrics.income_som.p50 == strategy(gen, "income")["metrics"]["income_som"]["p50"]
    client.get(f"{API}/runs/{run_id}/breakpoints")
    assert service.get_run_summary(run_id).breakpoints


def test_generate_with_scenario_gives_other_run():
    base = generate()
    dry = generate(scenario={"water_supply_factor": 0.7})
    assert dry["generation_id"] != base["generation_id"]
    assert (
        strategy(dry, "user")["metrics"]["max_yield_loss"]
        > strategy(base, "user")["metrics"]["max_yield_loss"]
    )
