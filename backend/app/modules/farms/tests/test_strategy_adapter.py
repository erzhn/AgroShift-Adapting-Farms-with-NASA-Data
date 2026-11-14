"""The planning screen must calculate its selected farm, never a substitute demo farm."""

import pytest

from app.core.errors import ProblemError
from app.modules.farms.demo import load_seed, seed_id
from app.modules.farms.strategy_adapter import strategy_inputs


def test_real_contracts_reach_strategy_engine():
    bundle = load_seed()
    inputs = strategy_inputs(bundle.farm, bundle.crops)
    assert inputs.status["farm"] == "service"
    assert {f.id for f in inputs.fields} == {str(f.id) for f in bundle.farm.fields}
    assert len(inputs.crops) == 5
    maize = inputs.crops[str(seed_id("crop/maize"))]
    source = next(c for c in bundle.crops if c.code == "maize")
    assert maize.params.is_feed  # Silage must not become grain in the bridge.
    assert maize.params.yield_t_ha == source.variants[0].yield_potential_t_ha
    assert maize.params.price_som_t == source.price.price_som
    assert sum(maize.params.cost_som_ha_by_month) == sum(
        c.cost_som_ha for c in source.variants[0].costs
    )
    assert maize.kc == (source.kc_ini, source.kc_mid, source.kc_end)
    assert inputs.econ.opening_cash_som == 150000
    assert inputs.econ.family_by_month == (10000,) * 12
    assert all(c.agro_status == "experimental" for c in inputs.crops.values())


def test_profile_zero_and_unknown_have_different_meanings():
    bundle = load_seed()
    bundle.farm.cash_accounts[0].balance_som = 0
    bundle.farm.herds[0].head_count = 0
    inputs = strategy_inputs(bundle.farm, bundle.crops)
    assert inputs.econ.opening_cash_som == 0
    assert sum(inputs.econ.feed_demand_dm_kg) == 0
    assert sum(inputs.econ.milk_income_by_month) == 0
    bundle.farm.cash_accounts = []
    with pytest.raises(ValueError, match="средства"):
        strategy_inputs(bundle.farm, bundle.crops)


def test_missing_season_and_missing_prices_do_not_become_demo_values():
    bundle = load_seed()
    bundle.crops[0].price = None
    inputs = strategy_inputs(bundle.farm, bundle.crops)
    assert inputs.crops[str(bundle.crops[0].id)].params.price_som_t is None
    bundle.farm.fields[0].seasons = []
    with pytest.raises(ValueError, match="каждом поле"):
        strategy_inputs(bundle.farm, bundle.crops)


def test_failed_real_farm_is_never_substituted(monkeypatch):
    from app.services import strategy_inputs as bridge

    def broken(*args):
        raise ValueError("Missing season")

    monkeypatch.setattr(bridge, "_find", lambda *args: broken)
    with pytest.raises(ProblemError):
        bridge.load_inputs(str(seed_id("farm/asan")))
    assert bridge.load_inputs("demo").status["farm"] == "stub"
