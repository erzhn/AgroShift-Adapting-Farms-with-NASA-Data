"""М13 — точка поломки.

ТЗ, раздел 8.13. Для каждого фактора сценария бинарным поиском находится минимальное
отклонение от базы, при котором медианный исход нарушает ограничение; для климатических
факторов считается историческая частота: в скольких из 30 лет NASA отклонение было не меньше.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Threshold:
    value: float | None  # None — в проверенном диапазоне план не ломается
    already_broken: bool = False  # ограничение нарушено уже в базовых условиях


def bisect_threshold(
    violates: Callable[[float], bool],
    base: float,
    limit: float,
    tol: float,
    max_iter: int = 12,
) -> Threshold:
    """Минимальное отклонение от `base` в сторону `limit`, при котором `violates` истинно.

    Предполагается монотонность: чем дальше от базы, тем хуже. `tol` — точность в единицах
    фактора. Возвращается значение на «сломанной» стороне отрезка.
    """
    if violates(base):
        return Threshold(base, already_broken=True)
    if not violates(limit):
        return Threshold(None)
    ok, bad = base, limit
    for _ in range(max_iter):
        if abs(bad - ok) <= tol:
            break
        mid = (ok + bad) / 2.0
        if violates(mid):
            bad = mid
        else:
            ok = mid
    return Threshold(bad)


def historical_frequency(
    year_values: Sequence[float], threshold: float, worse_is_lower: bool
) -> tuple[int, int]:
    """В скольких годах из истории значение фактора было не лучше порога: (N, из скольких)."""
    values = np.asarray(year_values, dtype=float)
    hit = values <= threshold if worse_is_lower else values >= threshold
    return int(hit.sum()), int(values.size)


def safety_margin(base: float, threshold: float, sigma: float) -> float | None:
    """Запас прочности — расстояние от базы до порога в стандартных отклонениях фактора."""
    if sigma <= 0:
        return None
    return abs(threshold - base) / sigma
