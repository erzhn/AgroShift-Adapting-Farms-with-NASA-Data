"""М9 — эталонные примеры 15.3 (кассовый разрыв) и 15.4 (сбыт) из ТЗ."""

import numpy as np
import pytest

from agroshift_core.cashflow import (
    cash_path,
    delay_payments,
    find_cash_gap,
    gap_probability,
    sell_with_channel,
)
from agroshift_core.plan_eval import (
    Conditions,
    CropParams,
    FarmEcon,
    Noise,
    PlanPart,
    evaluate_plan,
)

APR, MAY, SEP = 3, 4, 8
OPENING, RESERVE = 50_000, 10_000


def _flows(costs: dict[int, float], revenue: dict[int, float]) -> tuple[np.ndarray, np.ndarray]:
    inflow, outflow = np.zeros(12), np.zeros(12)
    for month, value in revenue.items():
        inflow[month] = value
    for month, value in costs.items():
        outflow[month] = value
    return inflow, outflow


def test_example_15_3_strategy_a_is_feasible():
    # А: маржа 70 тыс., стартовые затраты 40 тыс. в апреле
    inflow, outflow = _flows({APR: 40_000}, {SEP: 110_000})
    gap = find_cash_gap(cash_path(OPENING, inflow, outflow), RESERVE)
    assert gap.feasible
    assert gap.financing_needed_som == 0


def test_example_15_3_strategy_b_is_infeasible_despite_higher_margin():
    # Б: маржа 100 тыс., но 150 тыс. затрат до первого поступления в сентябре
    inflow, outflow = _flows({APR: 75_000, MAY: 75_000}, {SEP: 250_000})
    cash = cash_path(OPENING, inflow, outflow)
    assert cash[-1] - OPENING == 100_000  # маржа больше, чем у А
    gap = find_cash_gap(cash, RESERVE)
    assert not gap.feasible
    assert gap.first_month == APR  # разрыв уже в апреле
    assert gap.worst_month == MAY
    # сколько финансирования нужно: 150 − (50 − 10) = 110 тыс.
    assert gap.financing_needed_som == pytest.approx(110_000)


def test_example_15_4_sales_channel_limits_revenue():
    # урожай 6 т, канал сбыта берёт 2 т: 2 т по цене канала + 4 т по цене срочной реализации
    revenue, unsold = sell_with_channel(6.0, 50_000, max_volume_t=2.0, distress_factor=0.6)
    assert unsold == pytest.approx(4.0)
    assert revenue == pytest.approx(2 * 50_000 + 4 * 50_000 * 0.6)
    assert revenue < 6 * 50_000


def test_no_channel_limit_sells_everything():
    revenue, unsold = sell_with_channel(np.array([6.0, 1.0]), 50_000, None)
    assert unsold.tolist() == [0.0, 0.0]
    assert revenue.tolist() == [300_000, 50_000]


def test_payment_delay_moves_money_and_keeps_total():
    shipped = np.zeros(12)
    shipped[SEP] = 100_000
    received, receivable = delay_payments(shipped, 45)
    assert received[SEP] == 0
    assert received[SEP + 1] == pytest.approx(50_000)
    assert received[SEP + 2] == pytest.approx(50_000)
    assert receivable == pytest.approx(0)
    # платёж, ушедший за декабрь, не теряется, а становится дебиторкой
    received, receivable = delay_payments(shipped, 120)
    assert received.sum() == 0
    assert receivable == pytest.approx(100_000)


def test_gap_probability_counts_samples_below_reserve():
    cash = np.array([[50, 40, 30], [50, 5, 30], [50, 40, 9], [20, 20, 20]], dtype=float)
    assert gap_probability(cash, 10) == pytest.approx(0.5)


# --- то же через сборку плана: флаг «без покупателя» и «пропуск ≠ ноль» ---


def _farm(**kw) -> FarmEcon:
    zero = (0.0,) * 12
    base = dict(
        opening_cash_som=0, reserve_som=0, family_by_month=zero, debt_by_month=zero,
        milk_income_by_month=zero, herd_cost_by_month=zero, feed_demand_dm_kg=zero,
        feed_opening_stock_dm_kg=0, feed_price_som_t=10_000,
    )
    return FarmEcon(**{**base, **kw})


def _part(crop_id: str, area: float = 1.0, n: int = 3) -> PlanPart:
    return PlanPart("f", crop_id, area, np.ones(n), np.zeros((n, 36)), np.zeros((n, 36)))


def _noise(n: int = 3, *crops: str) -> Noise:
    return Noise(price={c: np.ones(n) for c in (*crops, "milk")}, feed=np.ones(n))


def _crop(crop_id: str, price, **kw) -> CropParams:
    sep = tuple(1.0 if m == SEP else 0.0 for m in range(12))
    return CropParams(crop_id, 6.0, price, (0.0,) * 12, sep, **kw)


def test_example_15_4_plan_flags_tonnes_without_buyer():
    crops = {"v": _crop("v", 50_000, max_volume_t=2.0, distress_factor=0.6)}
    res = evaluate_plan([_part("v")], crops, _farm(), Conditions(), _noise(3, "v"))
    assert res.unsold_t["v"].tolist() == pytest.approx([4.0] * 3)
    assert res.income.tolist() == pytest.approx([2 * 50_000 + 4 * 30_000] * 3)


def test_missing_price_is_partial_not_zero_revenue():
    crops = {"v": _crop("v", None)}
    res = evaluate_plan([_part("v")], crops, _farm(), Conditions(), _noise(3, "v"))
    assert res.completeness == "partial"
    assert "price:v" in res.unknown_inputs


def test_payment_delay_hits_cash_but_not_income():
    crops = {"v": _crop("v", 50_000)}
    args = ([_part("v")], crops, _farm())
    now = evaluate_plan(*args, Conditions(), _noise(3, "v"))
    late = evaluate_plan(*args, Conditions(payment_delay_days=60), _noise(3, "v"))
    assert late.income.tolist() == pytest.approx(now.income.tolist())
    assert late.cash[0, SEP] < now.cash[0, SEP]
    assert late.cash[0, -1] == pytest.approx(now.cash[0, -1])
