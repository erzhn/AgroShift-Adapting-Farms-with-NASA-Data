"""М11 — генератор стратегий: перебор утверждённых схем и выбор лучшей по каждой цели.

ТЗ, раздел 8.11; упрощение для хакатона (14.1): вместо MILP — полный перебор допустимых
вариантов по полям (≤ 500 комбинаций). Цели:

    income       max E[доход]                           P(разрыв) ≤ 10%
    resilient    max CVaR10 дохода                      P(разрыв) ≤ 5%
    water_light  min E[вода брутто в пиковые декады]    E[доход] ≥ 85% от income, P(разрыв) ≤ 10%
    user         без оптимизации — текущий план на тех же выборках

Если допустимых схем нет, стратегия не выдаётся: возвращается причина, искусственные
варианты не дорисовываются.
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


def select_strategies(
    mean_income: np.ndarray,
    cvar10: np.ndarray,
    p_gap: np.ndarray,
    peak_water_m3: np.ndarray,
    financing_needed: np.ndarray,
    user_index: int = 0,
) -> Selection:
    """Выбор схемы по каждой цели. Все массивы — по схемам, порядок детерминирован."""
    mean_income = np.asarray(mean_income, dtype=float)
    chosen: dict[str, int] = {"user": user_index}
    excluded: dict[str, dict] = {}

    def no_cash(limit: float) -> dict:
        best = int(np.argmin(p_gap))
        return {
            "constraint": "cash_reserve",
            "p_gap_limit": limit,
            "best_p_gap": float(p_gap[best]),
            "financing_needed_som": float(financing_needed[best]),
        }

    ok = p_gap <= P_GAP_LIMIT + 1e-9
    if ok.any():
        chosen["income"] = int(np.argmax(np.where(ok, mean_income, -np.inf)))
    else:
        excluded["income"] = no_cash(P_GAP_LIMIT)

    ok_res = p_gap <= P_GAP_RESILIENT + 1e-9
    if ok_res.any():
        chosen["resilient"] = int(np.argmax(np.where(ok_res, cvar10, -np.inf)))
    else:
        excluded["resilient"] = no_cash(P_GAP_RESILIENT)

    if "income" in chosen:
        top = mean_income[chosen["income"]]
        floor = top - (1.0 - WATER_LIGHT_INCOME_SHARE) * abs(top)
        ok_water = ok & (mean_income >= floor - 1e-9)
        # при равной воде — схема с большим доходом
        order = np.lexsort((-mean_income, np.where(ok_water, peak_water_m3, np.inf)))
        chosen["water_light"] = int(order[0])
    else:
        excluded["water_light"] = excluded["income"]

    return Selection(chosen, excluded)


def win_share(income_by_scheme: np.ndarray) -> np.ndarray:
    """Доля выборок, в которых схема лучшая по доходу (М17, устойчивость победителя)."""
    income = np.atleast_2d(np.asarray(income_by_scheme, dtype=float))
    winners = income.argmax(axis=0)
    return np.bincount(winners, minlength=income.shape[0]) / income.shape[1]
