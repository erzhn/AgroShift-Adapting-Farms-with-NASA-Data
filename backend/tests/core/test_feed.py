"""М8 — корма: свой или покупной, без двойного учёта."""

import numpy as np
import pytest

from agroshift_core.feed import feed_balance, herd_demand_dm_kg
from agroshift_core.plan_eval import (
    Conditions,
    CropParams,
    FarmEcon,
    Noise,
    PlanPart,
    evaluate_plan,
)

JUN, OCT = 5, 9


def test_demand_for_eight_cows_with_grazing():
    grazing = np.zeros(12)
    grazing[4:9] = 0.6  # май–сентябрь на пастбище
    demand = herd_demand_dm_kg(8, 14.0, grazing)
    assert demand[0] == pytest.approx(8 * 14 * 31)
    assert demand[6] == pytest.approx(8 * 14 * 31 * 0.4)


def test_enough_own_feed_means_no_purchase():
    demand = np.full(12, 1_000.0)
    harvest = np.zeros((1, 12))
    harvest[0, JUN] = 12_000
    fb = feed_balance(demand, harvest, opening_stock_dm_kg=5_000)
    assert fb.purchased_dm_kg.sum() == 0
    assert fb.sold_dm_kg.sum() == 0
    assert fb.stock_dm_kg[0, -1] == pytest.approx(5_000)  # запас на зиму восстановлен
    assert fb.self_sufficiency[0] == pytest.approx(1.0)


def test_shortage_is_bought_in_autumn_and_surplus_is_sold():
    demand = np.full(12, 1_000.0)
    harvest = np.zeros((2, 12))
    harvest[0, JUN] = 8_000  # не хватает 4 т
    harvest[1, JUN] = 15_000  # 3 т лишние
    fb = feed_balance(demand, harvest, opening_stock_dm_kg=5_000)
    assert fb.purchased_dm_kg[0, OCT] == pytest.approx(4_000)
    assert fb.sold_dm_kg[1, OCT] == pytest.approx(3_000)
    assert fb.self_sufficiency[0] == pytest.approx(1 - 4_000 / 12_000)
    assert (fb.stock_dm_kg >= -1e-9).all()


def test_empty_stock_is_bought_immediately():
    fb = feed_balance(np.full(12, 1_000.0), np.zeros((1, 12)), opening_stock_dm_kg=2_000)
    assert fb.purchased_dm_kg[0, 2] == pytest.approx(1_000)  # в марте запас кончился


def test_no_double_counting_of_own_feed():
    """Корм, скормленный своему скоту, не даёт выручки: его ценность — некупленный корм."""
    zero = (0.0,) * 12
    n = 2
    jun = tuple(1.0 if m == JUN else 0.0 for m in range(12))
    hay = CropParams("hay", 10.0, 9_000, zero, jun, is_feed=True, dm_share=1.0)
    part = PlanPart("f", "hay", 1.0, np.ones(n), np.zeros((n, 36)), np.zeros((n, 36)))
    noise = Noise(price={"hay": np.ones(n), "milk": np.ones(n)}, feed=np.ones(n))

    def farm(demand_per_month: float) -> FarmEcon:
        return FarmEcon(
            opening_cash_som=0, reserve_som=0, family_by_month=zero, debt_by_month=zero,
            milk_income_by_month=zero, herd_cost_by_month=zero,
            feed_demand_dm_kg=(demand_per_month,) * 12,
            feed_opening_stock_dm_kg=5 * demand_per_month,  # запас до укоса в июне
            feed_price_som_t=12_000, feed_dm_share=1.0,
        )

    # скот съедает ровно весь урожай: 10 т сена не продаются, выручки растениеводства нет
    eats_all = evaluate_plan([part], {"hay": hay}, farm(10_000 / 12), Conditions(), noise)
    assert eats_all.flows["crop_revenue"].sum() == 0
    assert eats_all.flows["feed_sales"].sum() == pytest.approx(0, abs=1)
    assert eats_all.flows["feed_purchase"].sum() == pytest.approx(0, abs=1)
    assert eats_all.income.tolist() == pytest.approx([0, 0], abs=1)
    assert eats_all.flows["feed_purchase"].sum() == pytest.approx(0, abs=1)
    assert eats_all.income.tolist() == pytest.approx([0, 0], abs=1)
    # без скота те же 10 т уходят на продажу по своей цене
    no_herd = evaluate_plan([part], {"hay": hay}, farm(0.0), Conditions(), noise)
    assert no_herd.flows["feed_sales"][0].sum() == pytest.approx(10 * 9_000)
    assert no_herd.flows["feed_purchase"].sum() == 0
