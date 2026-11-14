"""М8 — кормовой баланс и животные (упрощённо, по месяцам).

ТЗ, раздел 8.8. Правило без двойного учёта: корм, скормленный своему скоту, не даёт выручки
растениеводства — его ценность в том, что этот корм не пришлось покупать. Поэтому кормовая
культура вообще не проходит через продажу урожая: её урожай приходит сюда, и в деньги
попадают только покупка недостачи и продажа излишка.
"""

from dataclasses import dataclass

import numpy as np

DAYS_IN_MONTH = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], dtype=float)


def herd_demand_dm_kg(
    head_count: float,
    dmi_kg_day: float,
    grazing_share: np.ndarray,
) -> np.ndarray:
    """Потребность в заготовленном корме, кг сухого вещества по месяцам.

    D_m = N · DMI · days_m · (1 − доля выпаса_m).
    """
    grazing = np.clip(np.asarray(grazing_share, dtype=float), 0.0, 1.0)
    return head_count * dmi_kg_day * DAYS_IN_MONTH * (1.0 - grazing)


@dataclass(frozen=True)
class FeedBalance:
    """Результат кормового баланса; оси массивов — (выборки, 12 месяцев), кг СВ."""

    purchased_dm_kg: np.ndarray
    sold_dm_kg: np.ndarray
    stock_dm_kg: np.ndarray  # запас на конец месяца
    self_sufficiency: np.ndarray  # (выборки,) доля потребности, закрытая своим кормом


def feed_balance(
    demand_dm_kg: np.ndarray,
    harvest_dm_kg: np.ndarray,
    opening_stock_dm_kg: float,
    closing_target_dm_kg: float | None = None,
    stocking_month: int = 9,
) -> FeedBalance:
    """Помесячный баланс: запас + уборка − скормлено, недостача покупается.

    - Каждый месяц скот ест из запаса; если запас кончился — недостача покупается сразу.
    - В месяц заготовки (`stocking_month`, по умолчанию октябрь) хозяйство сводит баланс на
      зиму: докупает то, чего не хватит до конца года и на переходящий запас, либо продаёт
      излишек.
    - `closing_target_dm_kg` — запас, который должен остаться на 31 декабря (на зиму и весну
      следующего года). По умолчанию равен начальному: год не «проедает» чужой запас.
    """
    demand = np.asarray(demand_dm_kg, dtype=float)
    harvest = np.atleast_2d(np.asarray(harvest_dm_kg, dtype=float))
    n_samples, n_months = harvest.shape
    target = opening_stock_dm_kg if closing_target_dm_kg is None else closing_target_dm_kg

    purchased = np.zeros((n_samples, n_months))
    sold = np.zeros((n_samples, n_months))
    stock_path = np.zeros((n_samples, n_months))
    stock = np.full(n_samples, float(opening_stock_dm_kg))

    for m in range(n_months):
        stock = stock + harvest[:, m]
        if m == stocking_month:
            need = demand[m:].sum() + target
            expected = stock + harvest[:, m + 1 :].sum(axis=1)
            buy = np.maximum(0.0, need - expected)
            sell = np.minimum(np.maximum(0.0, expected - need), stock)
            purchased[:, m] += buy
            sold[:, m] += sell
            stock = stock + buy - sell
        fed = np.minimum(stock, demand[m])
        purchased[:, m] += demand[m] - fed  # запас пуст — покупаем и сразу скармливаем
        stock = stock - fed
        stock_path[:, m] = stock

    total_demand = demand.sum()
    if total_demand > 0:
        # покупка сверх потребности — это пополнение запаса, а не закрытие потребности года
        covered = 1.0 - np.minimum(purchased.sum(axis=1), total_demand) / total_demand
    else:
        covered = np.ones(n_samples)
    return FeedBalance(purchased, sold, stock_path, covered)
