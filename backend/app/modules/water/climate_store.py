"""Климат из снимков NASA POWER, подготовленный для расчёта (М1 + М2).

Читает Parquet-снимки из data/snapshots (без сети), прогоняет контроль качества,
поправку на высоту поля, сценарные сдвиги и считает ET0. Результат кэшируется.
"""

import math
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd

from agroshift_core import climate as m1
from agroshift_core import et0 as m2
from app.core.config import get_settings
from ingest import snapshots as store
from ingest.power import SOURCE as POWER_SOURCE


class NoSnapshotError(RuntimeError):
    """В data/snapshots нет снимков NASA POWER — запустите `python -m ingest.power`."""


@dataclass(frozen=True)
class PreparedClimate:
    """Суточные ряды одной ячейки, приведённые к полю."""

    meta: dict
    start: date
    dates: np.ndarray        # datetime64[D]
    doy: np.ndarray
    tmax: np.ndarray
    tmin: np.ndarray
    tmean: np.ndarray
    ws2m: np.ndarray
    rs: np.ndarray
    precip: np.ndarray
    rh_min: np.ndarray
    et0: np.ndarray
    hargreaves: np.ndarray   # True — день посчитан резервным методом
    qc: m1.QCReport
    temperature_shift_c: float

    @property
    def n(self) -> int:
        return int(self.dates.size)

    @property
    def et0_method(self) -> str:
        share = float(self.hargreaves.mean()) if self.n else 0.0
        return "penman_monteith" if share == 0 else ("hargreaves" if share == 1 else "mixed")

    def index_of(self, day: date) -> int:
        return (day - self.start).days

    def season_index(self, start_day: date, n_days: int) -> np.ndarray:
        """Индексы n_days суток, начиная со start_day. Если ряд кончился — берётся
        тот же день предыдущего года (нужно только для сезонов, уходящих за снимок)."""
        idx = self.index_of(start_day) + np.arange(n_days)
        while (idx >= self.n).any():
            idx = np.where(idx >= self.n, idx - 365, idx)
        return np.maximum(idx, 0)


def _dir():
    return get_settings().snapshots_dir


@lru_cache(maxsize=1)
def snapshot_metas() -> tuple[dict, ...]:
    """Последний снимок POWER для каждой точки."""
    latest: dict[str, dict] = {}
    for meta in store.list_snapshots(_dir(), source=POWER_SOURCE):
        key = meta.get("name") or meta["code"]
        if key not in latest or meta["fetched_at"] > latest[key]["fetched_at"]:
            latest[key] = meta
    return tuple(sorted(latest.values(), key=lambda m: m["code"]))


def clear_cache() -> None:
    snapshot_metas.cache_clear()
    _quality_controlled.cache_clear()
    prepared_climate.cache_clear()


def nearest_snapshot(lat: float | None, lon: float | None) -> dict:
    metas = snapshot_metas()
    if not metas:
        raise NoSnapshotError(NoSnapshotError.__doc__)
    if lat is None or lon is None:
        return metas[0]

    def distance(meta: dict) -> float:
        d_lat = math.radians(meta["lat"] - lat)
        d_lon = math.radians(meta["lon"] - lon) * math.cos(math.radians(lat))
        return math.hypot(d_lat, d_lon)

    return min(metas, key=distance)


@lru_cache(maxsize=16)
def _quality_controlled(code: str) -> tuple[pd.DataFrame, pd.DataFrame, m1.QCReport]:
    raw = store.load_snapshot(code, _dir())
    raw = raw.set_index(pd.DatetimeIndex(pd.to_datetime(raw["date"]))).drop(columns="date")
    raw = raw.asfreq("D")  # пропущенные сутки становятся явными пропусками
    return m1.quality_control(raw[list(m1.COLUMNS)])


@lru_cache(maxsize=128)
def prepared_climate(code: str, lat: float, elevation_m: float | None,
                     temp_delta_c: float = 0.0, precip_factor: float = 1.0) -> PreparedClimate:
    """Климат снимка для поля на высоте elevation_m со сценарными сдвигами."""
    meta = next(m for m in snapshot_metas() if m["code"] == code)
    df, norm_filled, qc = _quality_controlled(code)
    z_cell = float(meta["cell_elevation_m"])
    z_field = z_cell if elevation_m is None else float(elevation_m)

    # М1: поправка температур на высоту (6.3) + сценарный сдвиг ΔT
    shift = float(m1.altitude_correction(0.0, z_field, z_cell)) + temp_delta_c
    tmax = df["tmax"].to_numpy() + shift
    tmin = df["tmin"].to_numpy() + shift
    # влагосодержание воздуха не меняем: точка росы прежняя, но не выше Tmin
    tdew = np.minimum(df["tdew"].to_numpy(), tmin)
    ws2m = df["ws2m"].to_numpy()
    rs = df["rs"].to_numpy()
    precip = df["precip"].to_numpy() * precip_factor

    dates = df.index.to_numpy().astype("datetime64[D]")
    doy = df.index.dayofyear.to_numpy()

    # М2: Penman–Monteith; где радиация или ветер заполнены нормой — Hargreaves–Samani
    ea = m2.actual_vapour_pressure(tdew=tdew)
    et0_pm = m2.et0_penman_monteith(tmax, tmin, ea, ws2m, rs, lat, z_field, doy)
    et0_hs = m2.et0_hargreaves(tmax, tmin, lat, doy)
    use_hs = (norm_filled["rs"] | norm_filled["ws2m"]).to_numpy()
    et0 = np.where(use_hs, et0_hs, et0_pm)

    rh_min = np.clip(100.0 * ea / m2.saturation_vapour_pressure(tmax), 0.0, 100.0)

    return PreparedClimate(
        meta=meta, start=df.index[0].date(), dates=dates, doy=doy, tmax=tmax, tmin=tmin,
        tmean=(tmax + tmin) / 2.0, ws2m=ws2m, rs=rs, precip=precip, rh_min=rh_min,
        et0=et0, hargreaves=use_hs, qc=qc, temperature_shift_c=shift,
    )


def history_years(n_years: int = 30) -> list[int]:
    """Последние n_years полных календарных лет, общих для всех снимков."""
    metas = snapshot_metas()
    if not metas:
        raise NoSnapshotError(NoSnapshotError.__doc__)
    first, last = None, None
    for meta in metas:
        start = date.fromisoformat(meta["period_start"])
        end = date.fromisoformat(meta["period_end"])
        y0 = start.year if (start.month, start.day) == (1, 1) else start.year + 1
        y1 = end.year if (end.month, end.day) == (12, 31) else end.year - 1
        first = y0 if first is None else max(first, y0)
        last = y1 if last is None else min(last, y1)
    years = list(range(first, last + 1))
    return years[-n_years:]
