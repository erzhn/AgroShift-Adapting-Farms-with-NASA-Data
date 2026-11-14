"""М12 — стресс-тест и цена адаптации.

ТЗ, раздел 8.12. Три величины: A — исходный план в базовых условиях, B — исходный план в
новых условиях, C — исправленный план в новых условиях.

    Ущерб условий = A − B      Выигрыш адаптации = C − B
    Стоимость изменений = Capex_C + ΔVarCost

Исправленный план — лучший из схем, отличающихся от исходной минимальным числом полей.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations, product


def neighbours[T](
    scheme: Sequence[T], options_per_field: Sequence[Sequence[T]], max_changes: int = 1
) -> list[tuple[T, ...]]:
    """Схемы, отличающиеся от исходной не более чем в `max_changes` полях.

    Исходная схема всегда первая: «ничего не менять» — тоже кандидат.
    """
    base = tuple(scheme)
    result = [base]
    for k in range(1, max_changes + 1):
        for fields in combinations(range(len(base)), k):
            alternatives = [[o for o in options_per_field[f] if o != base[f]] for f in fields]
            for combo in product(*alternatives):
                candidate = list(base)
                for f, option in zip(fields, combo, strict=True):
                    candidate[f] = option
                result.append(tuple(candidate))
    return result


@dataclass(frozen=True)
class AdaptationPrice:
    damage_som: float  # A − B: сколько отняли новые условия
    gain_som: float  # C − B: сколько возвращает исправление
    change_cost_som: float  # Capex_C + ΔVarCost: сколько стоит само исправление


def adaptation_price(
    income_a: float,
    income_b: float,
    income_c: float,
    capex_original: float,
    capex_fixed: float,
    var_cost_original: float,
    var_cost_fixed: float,
) -> AdaptationPrice:
    return AdaptationPrice(
        damage_som=income_a - income_b,
        gain_som=income_c - income_b,
        change_cost_som=(capex_fixed - capex_original) + (var_cost_fixed - var_cost_original),
    )


def pick_fix(p_gap: Sequence[float], median_income: Sequence[float], p_gap_limit: float) -> int:
    """Индекс лучшего кандидата: сначала те, кто держит резерв, среди них — больший доход.

    Если резерв не держит никто — кандидат с наименьшей вероятностью разрыва.
    Индекс 0 (исходный план) выигрывает при равенстве: изменения должны быть оправданы.
    """
    indexed = range(len(p_gap))
    feasible = [i for i in indexed if p_gap[i] <= p_gap_limit + 1e-9]
    if feasible:
        return max(feasible, key=lambda i: (median_income[i], -i))
    return min(indexed, key=lambda i: (p_gap[i], -median_income[i], i))
