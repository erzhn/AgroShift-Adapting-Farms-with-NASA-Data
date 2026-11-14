"""М3 — потребность культуры ETc = Kc(t) × ET0 (раздел 8.3 ТЗ).

Kc(t) — кусочно-линейная кривая FAO-56 по четырём стадиям:
начальная (Kc_ini) -> развитие (линейно до Kc_mid) -> середина (Kc_mid) -> поздняя (до Kc_end).

Уточнение Kc по NDVI (HLS) — этап «развитие», здесь не реализовано.
"""

import numpy as np

STAGES = ("ini", "dev", "mid", "late")
INITIAL_ROOT_DEPTH_M = 0.15


def stage_lengths_from_gdd(gdd_daily: np.ndarray, stage_days: tuple[int, int, int, int],
                           gdd_required: float) -> tuple[int, int, int, int]:
    """Длина стадий в днях по накопленным GDD: в жаркий год стадии короче (8.3).

    Пороги стадий — доли gdd_required, пропорциональные справочным длинам stage_days.
    gdd_daily должен покрывать сезон с запасом; если тепла не хватило,
    последняя стадия тянется до конца ряда.
    """
    total_days = float(sum(stage_days))
    thresholds = gdd_required * np.cumsum(stage_days) / total_days
    cumulative = np.cumsum(gdd_daily)
    # день (1-based), в который накопленная сумма впервые достигла порога
    ends = np.searchsorted(cumulative, thresholds, side="left") + 1
    ends = np.minimum(ends, len(gdd_daily))
    ends = np.maximum.accumulate(ends)
    lengths = np.diff(np.concatenate(([0], ends)))
    # у каждой стадии минимум один день
    lengths = np.maximum(lengths, 1)
    overflow = int(lengths.sum()) - len(gdd_daily)
    if overflow > 0:
        lengths[-1] = max(1, lengths[-1] - overflow)
    return tuple(int(x) for x in lengths)


def stage_index(lengths: tuple[int, int, int, int]) -> np.ndarray:
    """Номер стадии 0..3 для каждого дня сезона."""
    return np.repeat(np.arange(4), lengths)


def kc_curve(lengths: tuple[int, int, int, int], kc_ini: float, kc_mid: float,
             kc_end: float) -> np.ndarray:
    """Суточная кривая Kc (FAO-56, ур. 66)."""
    l_ini, l_dev, l_mid, l_late = lengths
    return np.concatenate([
        np.full(l_ini, kc_ini),
        kc_ini + (np.arange(1, l_dev + 1) / l_dev) * (kc_mid - kc_ini),
        np.full(l_mid, kc_mid),
        kc_mid + (np.arange(1, l_late + 1) / l_late) * (kc_end - kc_mid),
    ])


def adjust_kc_for_climate(kc_table: float, u2_mean: float, rh_min_mean: float,
                          height_m: float) -> float:
    """Коррекция Kc_mid / Kc_end на климат (FAO-56, ур. 62).

    Kc = Kc_табл + [0,04·(u2 − 2) − 0,004·(RHmin − 45)]·(h/3)^0,3.
    Применима при u2 1–6 м/с, RHmin 20–80 %, h 0,1–10 м — значения обрезаются.
    """
    u2 = float(np.clip(u2_mean, 1.0, 6.0))
    rh_min = float(np.clip(rh_min_mean, 20.0, 80.0))
    h = float(np.clip(height_m, 0.1, 10.0))
    return kc_table + (0.04 * (u2 - 2.0) - 0.004 * (rh_min - 45.0)) * (h / 3.0) ** 0.3


def root_depth_curve(lengths: tuple[int, int, int, int], root_depth_max_m: float,
                     perennial: bool = False,
                     initial_m: float = INITIAL_ROOT_DEPTH_M) -> np.ndarray:
    """Глубина корней Z_r по дням: 0,15 м в начальной стадии, линейный рост в стадии
    развития до root_depth_max_m (8.4). У многолетних корни взрослые весь сезон."""
    n = int(sum(lengths))
    if perennial or root_depth_max_m <= initial_m:
        return np.full(n, root_depth_max_m)
    l_ini, l_dev, l_mid, l_late = lengths
    return np.concatenate([
        np.full(l_ini, initial_m),
        initial_m + (np.arange(1, l_dev + 1) / l_dev) * (root_depth_max_m - initial_m),
        np.full(l_mid + l_late, root_depth_max_m),
    ])


def crop_et(et0: np.ndarray, kc: np.ndarray) -> np.ndarray:
    """ETc = Kc × ET0, мм/сут."""
    return np.asarray(kc) * np.asarray(et0)
