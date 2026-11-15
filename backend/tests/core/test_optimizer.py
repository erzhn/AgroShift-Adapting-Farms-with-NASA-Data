"""М11–М13 — перебор схем, выбор по целям, соседи для исправления, бинарный поиск порога."""

import numpy as np
import pytest

from agroshift_core.breakpoints import bisect_threshold, historical_frequency, safety_margin
from agroshift_core.optimizer import enumerate_schemes, select_strategies, win_share
from agroshift_core.stress import adaptation_price, neighbours, pick_fix
from agroshift_core.uncertainty import cvar, lognormal_noise, result_hash


def test_enumeration_is_capped_and_starts_with_current_plan():
    schemes, truncated = enumerate_schemes([["a0", "a1"], ["b0", "b1", "b2"]])
    assert schemes[0] == ("a0", "b0")
    assert len(schemes) == 6 and not truncated
    schemes, truncated = enumerate_schemes([list(range(10))] * 3)
    assert len(schemes) == 500 and truncated


def test_selection_by_goal():
    #                     user   доходная  устойчивая  водная   рискованная
    mean = np.array([100.0, 150.0, 120.0, 130.0, 300.0])
    cv10 = np.array([40.0, 60.0, 110.0, 70.0, -50.0])
    pgap = np.array([0.30, 0.08, 0.00, 0.05, 0.60])
    peak = np.array([900.0, 950.0, 800.0, 500.0, 100.0])
    sel = select_strategies(mean, cv10, pgap, peak, np.zeros(5))
    assert sel.chosen == {"user": 0, "income": 1, "resilient": 2, "water_light": 3}
    assert not sel.excluded


def test_water_light_keeps_85_percent_of_income():
    mean = np.array([100.0, 200.0, 160.0, 175.0])
    peak = np.array([900.0, 900.0, 100.0, 400.0])
    sel = select_strategies(mean, mean, np.zeros(4), peak, np.zeros(4))
    # схема 2 экономит больше воды, но её доход ниже 85% от лучшего (170)
    assert sel.chosen["water_light"] == 3


def test_no_feasible_scheme_returns_reason_not_artificial_strategy():
    pgap = np.array([0.9, 0.4, 0.7])
    need = np.array([90_000.0, 25_000.0, 60_000.0])
    sel = select_strategies(np.ones(3), np.ones(3), pgap, np.ones(3), need)
    assert sel.chosen == {"user": 0}
    assert set(sel.excluded) == {"income", "resilient", "water_light"}
    assert sel.excluded["income"]["constraint"] == "cash_reserve"
    assert sel.excluded["income"]["best_p_gap"] == pytest.approx(0.4)
    assert sel.excluded["income"]["financing_needed_som"] == pytest.approx(25_000)


def test_no_feasible_scheme_with_financing_gives_best_per_goal_and_amount():
    #                user   доходная  устойчивая  водная
    mean = np.array([100.0, 200.0, 150.0, 180.0])
    cv10 = np.array([40.0, 60.0, 110.0, 70.0])
    pgap = np.array([0.7, 0.4, 0.3, 0.5])
    peak = np.array([900.0, 950.0, 800.0, 500.0])
    fin10 = np.array([90_000.0, 80_000.0, 50_000.0, 60_000.0])
    fin5 = fin10 + 10_000
    sel = select_strategies(
        mean, cv10, pgap, peak, fin10, financing_at_limit=fin10, financing_at_resilient=fin5
    )
    assert sel.chosen == {"user": 0, "income": 1, "resilient": 2, "water_light": 3}
    assert sel.financed == {"income": 80_000, "resilient": 60_000, "water_light": 60_000}
    assert not sel.excluded


def test_financing_fallback_skips_rotation_violations_and_keeps_feasible_goals():
    pgap = np.array([0.7, np.inf, 0.04])  # схема 1 нарушает севооборот
    mean = np.array([100.0, 999.0, 120.0])
    fin = np.array([50_000.0, 0.0, 0.0])
    sel = select_strategies(
        mean, mean, pgap, np.ones(3), fin, financing_at_limit=fin, financing_at_resilient=fin
    )
    assert sel.chosen["income"] == 2 and sel.chosen["resilient"] == 2
    assert not sel.financed  # допустимая схема есть — финансирование не нужно
    only_bad = select_strategies(
        mean[:2],
        mean[:2],
        np.array([np.inf, np.inf]),
        np.ones(2),
        fin[:2],
        financing_at_limit=fin[:2],
        financing_at_resilient=fin[:2],
    )
    assert set(only_bad.excluded) == {"income", "resilient", "water_light"}


def test_win_share():
    income = np.array([[1, 5, 5, 1], [2, 1, 1, 0]])
    assert win_share(income).tolist() == [0.75, 0.25]


def test_neighbours_keep_original_first_and_limit_changes():
    options = [["a0", "a1"], ["b0", "b1", "b2"], ["c0"]]
    one = neighbours(("a0", "b0", "c0"), options, 1)
    assert one[0] == ("a0", "b0", "c0")
    assert set(one[1:]) == {("a1", "b0", "c0"), ("a0", "b1", "c0"), ("a0", "b2", "c0")}
    assert len(neighbours(("a0", "b0", "c0"), options, 2)) == 6


def test_pick_fix_prefers_feasible_then_income_then_original():
    assert pick_fix([0.5, 0.05, 0.0], [900, 700, 600], 0.10) == 1
    assert pick_fix([0.05, 0.05], [700, 700], 0.10) == 0  # равенство — ничего не менять
    assert pick_fix([0.9, 0.4], [900, 100], 0.10) == 1  # никто не держит резерв


def test_adaptation_price_formulas():
    price = adaptation_price(800, 650, 700, 0, 60, 246, 200)
    assert (price.damage_som, price.gain_som, price.change_cost_som) == (150, 50, 14)


def test_bisect_finds_minimal_breaking_deviation():
    down = bisect_threshold(lambda v: v < 0.82, 1.0, 0.3, 0.005)
    assert down.value == pytest.approx(0.82, abs=0.006) and down.value < 0.82
    up = bisect_threshold(lambda v: v > 1.37, 1.0, 2.5, 0.01)
    assert up.value == pytest.approx(1.37, abs=0.011) and up.value > 1.37
    assert bisect_threshold(lambda v: False, 1.0, 0.3, 0.01).value is None
    assert bisect_threshold(lambda v: True, 1.0, 0.3, 0.01).already_broken


def test_historical_frequency_and_margin():
    years = [1.05, 0.95, 0.80, 0.78, 1.00]
    assert historical_frequency(years, 0.82, worse_is_lower=True) == (2, 5)
    assert historical_frequency([0.1, 1.5, 2.2], 1.4, worse_is_lower=False) == (2, 3)
    assert safety_margin(1.0, 0.82, 0.09) == pytest.approx(2.0)


def test_noise_is_reproducible_and_independent_of_other_keys():
    a = lognormal_noise(42, "price:corn", 30, 0.15)
    assert np.array_equal(a, lognormal_noise(42, "price:corn", 30, 0.15))
    assert not np.array_equal(a, lognormal_noise(43, "price:corn", 30, 0.15))
    assert not np.array_equal(a, lognormal_noise(42, "price:beans", 30, 0.15))
    assert lognormal_noise(1, "x", 20_000, 0.15).mean() == pytest.approx(1.0, abs=0.01)


def test_cvar_and_hash():
    assert cvar(np.arange(1, 21), 0.10) == pytest.approx(1.5)
    assert result_hash({"b": 1, "a": [1, 2]}) == result_hash({"a": [1, 2], "b": 1})
