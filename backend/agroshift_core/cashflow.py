"""М9 — денежный поток по месяцам, кассовый разрыв.

ТЗ, раздел 8.9:
    Cash_m = Cash_{m-1} + Rev_m − VarCost_m − Feed_m − Capex_m − Debt_m − Family_m + Subsidy_m

Все функции векторизованы: последняя ось — месяцы, ведущие оси — выборки.
Деньги внутри расчёта — float, округление до целых сомов делает слой API.
"""

from dataclasses import dataclass

import numpy as np


def sell_with_channel(
    volume_t: np.ndarray | float,
    price_som_t: np.ndarray | float,
    max_volume_t: float | None,
    distress_factor: float = 0.6,
) -> tuple[np.ndarray, np.ndarray]:
    """Выручка с учётом ёмкости канала сбыта (пример 15.4).

    До `max_volume_t` товар уходит по цене канала, остаток — по цене срочной реализации
    (`distress_factor` × цена). Возвращает (выручка, объём без покупателя, т).
    """
    volume = np.asarray(volume_t, dtype=float)
    price = np.asarray(price_som_t, dtype=float)
    if max_volume_t is None:
        return volume * price, np.zeros_like(volume)
    in_channel = np.minimum(volume, max_volume_t)
    unsold = volume - in_channel
    return in_channel * price + unsold * price * distress_factor, unsold


def delay_payments(shipped: np.ndarray, delay_days: float) -> tuple[np.ndarray, np.ndarray]:
    """Деньги приходят через `delay_days` после отгрузки.

    Задержка переводится в месяцы (30 дней); дробная часть делит платёж между двумя соседними
    месяцами. Возвращает (поступления по месяцам, дебиторка за горизонтом расчёта).
    """
    shipped = np.asarray(shipped, dtype=float)
    n = shipped.shape[-1]
    shift = max(0.0, float(delay_days)) / 30.0
    lo = int(np.floor(shift))
    frac = shift - lo
    received = np.zeros_like(shipped)
    for k, weight in ((lo, 1.0 - frac), (lo + 1, frac)):
        if weight > 0 and k < n:
            received[..., k:] += weight * shipped[..., : n - k]
    receivable = shipped.sum(axis=-1) - received.sum(axis=-1)
    return received, receivable


def cash_path(opening_cash: float, inflow: np.ndarray, outflow: np.ndarray) -> np.ndarray:
    """Остаток на конец каждого месяца."""
    return opening_cash + np.cumsum(np.asarray(inflow) - np.asarray(outflow), axis=-1)


@dataclass(frozen=True)
class CashGap:
    """Кассовый разрыв одной траектории остатка."""

    first_month: int | None  # индекс месяца 0..n-1; None — разрыва нет
    worst_month: int | None
    depth_som: float  # min(Cash_m − reserve); отрицательное число при разрыве
    financing_needed_som: float  # сколько денег нужно привлечь, чтобы разрыва не было

    @property
    def feasible(self) -> bool:
        return self.first_month is None


def find_cash_gap(cash: np.ndarray, reserve_som: float) -> CashGap:
    """Первый месяц с Cash_m < reserve и глубина разрыва (раздел 8.9)."""
    margin = np.asarray(cash, dtype=float) - reserve_som
    below = np.flatnonzero(margin < -1e-6)
    depth = float(margin.min())
    if below.size == 0:
        return CashGap(None, None, depth, 0.0)
    return CashGap(int(below[0]), int(margin.argmin()), depth, float(-depth))


def gap_probability(cash: np.ndarray, reserve_som: float) -> float:
    """Доля выборок, в которых остаток хотя бы раз опускается ниже резерва."""
    cash = np.atleast_2d(np.asarray(cash, dtype=float))
    return float(((cash - reserve_som).min(axis=-1) < -1e-6).mean())
