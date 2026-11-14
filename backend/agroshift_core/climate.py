"""М1 — подготовка климата (разделы 6.3 и 8.1 ТЗ).

Шаги: контроль качества -> поправка температур на высоту -> производные ряды
(GDD, заморозки, жаркие дни, нормы и процентили по декадам).

Quantile mapping по наземной станции (8.1) не реализован: станции в MVP нет.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from agroshift_core.calendar import decade_indices

COLUMNS = ("t2m", "tmax", "tmin", "tdew", "rh", "ws2m", "rs", "precip")

# Допустимые диапазоны (6.3): T ∈ [−45; 50] °C, RH ∈ [0; 100] %, осадки ≥ 0
RANGES: dict[str, tuple[float, float]] = {
    "t2m": (-45.0, 50.0),
    "tmax": (-45.0, 50.0),
    "tmin": (-45.0, 50.0),
    "tdew": (-60.0, 40.0),
    "rh": (0.0, 100.0),
    "ws2m": (0.0, 40.0),
    "rs": (0.0, 45.0),
    "precip": (0.0, 500.0),
}

FILL_VALUE = -999.0
MAX_INTERPOLATION_GAP = 3          # суток (6.3)
LAPSE_RATE_C_PER_M = -0.0065       # градиент температуры (6.3, 8.1)
HOT_DAY_TMAX_C = 35.0              # «жаркий день» (8.1)


@dataclass(frozen=True)
class QCReport:
    """Что сделал контроль качества — уходит в «откуда это число»."""

    n_days: int
    missing: dict[str, int] = field(default_factory=dict)        # пропуски и −999
    out_of_range: dict[str, int] = field(default_factory=dict)   # вне диапазона
    interpolated: dict[str, int] = field(default_factory=dict)   # пропуски ≤ 3 суток
    climatology: dict[str, int] = field(default_factory=dict)    # заполнено нормой

    @property
    def is_clean(self) -> bool:
        return not any(self.missing.values()) and not any(self.out_of_range.values())


def quality_control(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, QCReport]:
    """Контроль качества суточных рядов (6.3).

    df: колонки COLUMNS, индекс — DatetimeIndex с шагом сутки.
    Возвращает (очищенные ряды без NaN, булева маска «заполнено нормой», отчёт).

    −999 и значения вне диапазона -> пропуск; пропуски до 3 суток — линейная интерполяция;
    длиннее — климатическая норма дня года с пометкой.
    """
    out = df.copy()
    norm_filled = pd.DataFrame(False, index=df.index, columns=list(df.columns))
    missing, out_of_range, interpolated, climatology = {}, {}, {}, {}
    doy = df.index.dayofyear

    for col in df.columns:
        s = out[col].astype("float64")
        s = s.mask(np.isclose(s, FILL_VALUE))
        missing[col] = int(s.isna().sum())

        lo, hi = RANGES.get(col, (-np.inf, np.inf))
        bad = (s < lo) | (s > hi)
        out_of_range[col] = int(bad.sum())
        s = s.mask(bad)

        isna = s.isna()
        if isna.any():
            run_id = (isna != isna.shift()).cumsum()
            run_len = isna.groupby(run_id).transform("sum")
            short = isna & (run_len <= MAX_INTERPOLATION_GAP)
            filled = s.interpolate(method="linear", limit_area="inside")
            s = s.where(~short, filled)
            interpolated[col] = int((short & s.notna()).sum())

            still = s.isna()
            if still.any():
                norm = s.groupby(doy).transform("mean")
                s = s.fillna(norm).fillna(s.mean())
                norm_filled[col] = still
            climatology[col] = int(still.sum())
        else:
            interpolated[col] = 0
            climatology[col] = 0
        out[col] = s

    report = QCReport(len(df), missing, out_of_range, interpolated, climatology)
    return out, norm_filled, report


def altitude_correction(temp_c, z_field_m: float, z_cell_m: float,
                        lapse_rate: float = LAPSE_RATE_C_PER_M):
    """T_field = T_cell − 0,0065·(z_field − z_cell)  (8.1)."""
    return temp_c + lapse_rate * (z_field_m - z_cell_m)


def gdd_daily(tmax, tmin, t_base: float):
    """Суточная сумма активных температур: max(0, (Tmax + Tmin)/2 − T_base)  (8.1)."""
    return np.maximum(0.0, (np.asarray(tmax) + np.asarray(tmin)) / 2.0 - t_base)


def frost_dates(dates: np.ndarray, tmin: np.ndarray,
                threshold_c: float = 0.0) -> dict[int, dict[str, str | None]]:
    """Последний весенний и первый осенний заморозок (Tmin < порога) по годам (8.1)."""
    dates = np.asarray(dates, dtype="datetime64[D]")
    years = dates.astype("datetime64[Y]").astype(int) + 1970
    doy = (dates - dates.astype("datetime64[Y]").astype("datetime64[D]")).astype(int) + 1
    frost = np.asarray(tmin) < threshold_c
    result: dict[int, dict[str, str | None]] = {}
    for year in np.unique(years):
        in_year = years == year
        spring = dates[in_year & frost & (doy <= 182)]
        autumn = dates[in_year & frost & (doy > 182)]
        result[int(year)] = {
            "last_spring_frost": str(spring[-1]) if spring.size else None,
            "first_autumn_frost": str(autumn[0]) if autumn.size else None,
        }
    return result


def decade_norms(dates: np.ndarray, sums: dict[str, np.ndarray],
                 means: dict[str, np.ndarray], tmax: np.ndarray | None = None) -> pd.DataFrame:
    """Климатические нормы и процентили P10/P50/P90 по каждой из 36 декад (8.1).

    sums  — ряды, которые за декаду суммируются (осадки, ET0);
    means — ряды, которые усредняются (температуры);
    tmax  — если задан, считается среднее число дней с Tmax > 35 °C.
    Процентили берутся по годам.
    """
    dates = np.asarray(dates, dtype="datetime64[D]")
    frame = pd.DataFrame({
        "year": dates.astype("datetime64[Y]").astype(int) + 1970,
        "decade": decade_indices(dates),
    })
    agg: dict[str, str] = {}
    for name, values in sums.items():
        frame[name] = values
        agg[name] = "sum"
    for name, values in means.items():
        frame[name] = values
        agg[name] = "mean"
    if tmax is not None:
        frame["hot_days"] = (np.asarray(tmax) > HOT_DAY_TMAX_C).astype(float)
        agg["hot_days"] = "sum"

    per_year = frame.groupby(["year", "decade"]).agg(agg).reset_index()
    rows = []
    for decade, group in per_year.groupby("decade"):
        row: dict[str, float] = {"decade": int(decade)}
        for name in agg:
            values = group[name].to_numpy()
            if name == "hot_days":
                row["hot_days_mean"] = float(values.mean())
                continue
            p10, p50, p90 = np.percentile(values, [10, 50, 90])
            row[f"{name}_p10"], row[f"{name}_p50"], row[f"{name}_p90"] = (
                float(p10), float(p50), float(p90))
        rows.append(row)
    return pd.DataFrame(rows)
