"""М6 — урожай при дефиците воды и тепловом стрессе (раздел 8.6 ТЗ).

FAO-33, по стадиям с умножением (дефицит в цветение бьёт сильнее, чем в начале):

    Ya/Ym = Π_s [1 − Ky_s·(1 − ΣETa_s / ΣETc_s)] · F_heat · F_frost

Результат — «модельная оценка»: показывается с диапазоном и не точнее 0,1 т/га.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class StageYield:
    stage: int          # 0..3: ini, dev, mid, late
    days: int
    etc_mm: float
    eta_mm: float
    ratio: float        # ETa / ETc
    ky: float
    factor: float       # множитель урожая стадии


def stage_factor(eta_sum: float, etc_sum: float, ky: float) -> float:
    """Множитель урожая стадии: 1 − Ky·(1 − ETa/ETc), в пределах 0..1."""
    if etc_sum <= 0:
        return 1.0
    ratio = min(max(eta_sum / etc_sum, 0.0), 1.0)
    return float(min(max(1.0 - ky * (1.0 - ratio), 0.0), 1.0))


def water_factor_by_stage(eta: np.ndarray, etc: np.ndarray, stage_idx: np.ndarray,
                          ky_stages) -> tuple[float, list[StageYield]]:
    """Произведение множителей по четырём стадиям + разбор по стадиям."""
    total = 1.0
    details: list[StageYield] = []
    for s in range(4):
        mask = stage_idx == s
        etc_sum = float(etc[mask].sum())
        eta_sum = float(eta[mask].sum())
        factor = stage_factor(eta_sum, etc_sum, float(ky_stages[s]))
        ratio = eta_sum / etc_sum if etc_sum > 0 else 1.0
        details.append(StageYield(s, int(mask.sum()), etc_sum, eta_sum, ratio,
                                  float(ky_stages[s]), factor))
        total *= factor
    return total, details


def water_factor_seasonal(eta: np.ndarray, etc: np.ndarray, ky: float) -> float:
    """Сезонная формула FAO-33 — когда Ky по стадиям неизвестны."""
    return stage_factor(float(np.sum(eta)), float(np.sum(etc)), ky)


def heat_factor(hot_days: int, k_heat: float | None) -> float:
    """F_heat = max(0, 1 − k_heat · число дней с Tmax > T_crit в фазу цветения)."""
    if not k_heat or hot_days <= 0:
        return 1.0
    return max(0.0, 1.0 - k_heat * hot_days)


def frost_factor(frost_days: int, k_frost: float | None) -> float:
    """F_frost = max(0, 1 − k_frost · число дней с Tmin < t_min_kill в цветение сада)."""
    if not k_frost or frost_days <= 0:
        return 1.0
    return max(0.0, 1.0 - k_frost * frost_days)


def relative_yield(f_water: float, f_heat: float = 1.0, f_frost: float = 1.0) -> float:
    """Ya/Ym."""
    return float(min(max(f_water * f_heat * f_frost, 0.0), 1.0))


def round_yield(t_ha: float | None) -> float | None:
    """Урожай показывается не точнее 0,1 т/га."""
    return None if t_ha is None else round(float(t_ha), 1)
