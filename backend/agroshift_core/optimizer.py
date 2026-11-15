"""М11 — генератор стратегий: перебор утверждённых схем и выбор лучшей по каждой цели.

ТЗ, раздел 8.11; упрощение для хакатона (14.1): вместо MILP — полный перебор допустимых
вариантов по полям (≤ 500 комбинаций). Цели:

    income       max E[доход]                           P(разрыв) ≤ 10%
    resilient    max CVaR10 дохода                      P(разрыв) ≤ 5%
    water_light  min E[вода брутто в пиковые декады]    E[доход] ≥ 85% от income, P(разрыв) ≤ 10%
    user         без оптимизации — текущий план на тех же выборках

Если ни одна схема не держит резерв семьи, а суммы финансирования по схемам известны,
выдаётся лучшая по той же цели схема с пометкой «нужно финансирование X сом к месяцу M»
(пример 15.3: «сообщить, сколько финансирования нужно и когда»). Это реальная схема из
перебора, а не дорисованный вариант. Если допустимых схем нет совсем (все нарушают
севооборот) или суммы не переданы — стратегия не выдаётся, возвращается причина.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import islice, product

import numpy as np

MAX_SCHEMES = 500
P_GAP_LIMIT = 0.10
P_GAP_RESILIENT = 0.05
WATER_LIGHT_INCOME_SHARE = 0.85


def enumerate_schemes[T](
    options_per_field: Sequence[Sequence[T]], limit: int = MAX_SCHEMES
) -> tuple[list[tuple[T, ...]], bool]:
    """Все комбинации «по одному варианту на поле» в детерминированном порядке.

    Возвращает (схемы, обрезано ли). Первый вариант каждого поля — текущий план, поэтому
    схема с индексом 0 — это «Мой вариант».
    """
    total = 1
    for options in options_per_field:
        total *= max(1, len(options))
    schemes = list(islice(product(*options_per_field), limit))
    return schemes, total > limit


@dataclass(frozen=True)
class Selection:
    chosen: dict[str, int]  # тип стратегии -> индекс схемы
    excluded: dict[str, dict] = field(default_factory=dict)  # тип -> причина
    financed: dict[str, float] = field(default_factory=dict)  # тип -> сколько привлечь, сом


def select_strategies(
    mean_income: np.ndarray,
    cvar10: np.ndarray,
    p_gap: np.ndarray,
    peak_water_m3: np.ndarray,
    financing_needed: np.ndarray,
    user_index: int = 0,
    financing_at_limit: np.ndarray | None = None,
    financing_at_resilient: np.ndarray | None = None,
) -> Selection:
    """Выбор схемы по каждой цели. Все массивы — по схемам, порядок детерминирован.

    `p_gap` = inf помечает схему, которая в оптимизации не участвует (нарушен севооборот).
    `financing_at_limit` / `financing_at_resilient` — сколько денег нужно схеме, чтобы
    разрыв был не чаще 10% / 5% лет; без них схемы сверх лимита не выдаются.
    """
    mean_income = np.asarray(mean_income, dtype=float)
    cvar10 = np.asarray(cvar10, dtype=float)
    p_gap = np.asarray(p_gap, dtype=float)
    chosen: dict[str, int] = {"user": user_index}
    excluded: dict[str, dict] = {}
    financed: dict[str, float] = {}
    valid = np.isfinite(p_gap)

    def no_cash(limit: float) -> dict:
        best = int(np.argmin(p_gap))
        return {
            "constraint": "cash_reserve",
            "p_gap_limit": limit,
            "best_p_gap": float(p_gap[best]),
            "financing_needed_som": float(financing_needed[best]),
        }

    def best_of(objective: np.ndarray, mask: np.ndarray) -> int:
        return int(np.argmax(np.where(mask, objective, -np.inf)))

    ok = p_gap <= P_GAP_LIMIT + 1e-9
    income_pool = ok
    if ok.any():
        chosen["income"] = best_of(mean_income, ok)
    elif financing_at_limit is not None and valid.any():
        income_pool = valid
        chosen["income"] = best_of(mean_income, valid)
        financed["income"] = float(financing_at_limit[chosen["income"]])
    else:
        excluded["income"] = no_cash(P_GAP_LIMIT)

    ok_res = p_gap <= P_GAP_RESILIENT + 1e-9
    if ok_res.any():
        chosen["resilient"] = best_of(cvar10, ok_res)
    elif financing_at_resilient is not None and valid.any():
        chosen["resilient"] = best_of(cvar10, valid)
        financed["resilient"] = float(financing_at_resilient[chosen["resilient"]])
    else:
        excluded["resilient"] = no_cash(P_GAP_RESILIENT)

    if "income" in chosen:
        top = mean_income[chosen["income"]]
        floor = top - (1.0 - WATER_LIGHT_INCOME_SHARE) * abs(top)
        ok_water = income_pool & (mean_income >= floor - 1e-9)
        # при равной воде — схема с большим доходом
        order = np.lexsort((-mean_income, np.where(ok_water, peak_water_m3, np.inf)))
        chosen["water_light"] = int(order[0])
        if "income" in financed and financing_at_limit is not None:
            financed["water_light"] = float(financing_at_limit[chosen["water_light"]])
    else:
        excluded["water_light"] = excluded["income"]

    return Selection(chosen, excluded, financed)


def win_share(income_by_scheme: np.ndarray) -> np.ndarray:
    """Доля выборок, в которых схема лучшая по доходу (М17, устойчивость победителя)."""
    income = np.atleast_2d(np.asarray(income_by_scheme, dtype=float))
    winners = income.argmax(axis=0)
    return np.bincount(winners, minlength=income.shape[0]) / income.shape[1]
