"""М1–М3: декады, контроль качества, ET0 (эталон FAO-56), Kc."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from agroshift_core import calendar as cal
from agroshift_core import climate as m1
from agroshift_core import crop_et as m3
from agroshift_core import et0 as m2

# ---------------------------------------------------------------- декады (индекс 1..36)


def test_decade_index_bounds():
    assert cal.decade_index(date(2026, 1, 1)) == 1
    assert cal.decade_index(date(2026, 7, 20)) == 20
    assert cal.decade_index(date(2026, 7, 21)) == 21   # третья декада июля
    assert cal.decade_index(date(2026, 7, 31)) == 21
    assert cal.decade_index(date(2026, 12, 31)) == 36


def test_decade_bounds_third_decade_runs_to_month_end():
    assert cal.decade_bounds(2024, 6) == (date(2024, 2, 21), date(2024, 2, 29))
    assert cal.decade_bounds(2026, 21) == (date(2026, 7, 21), date(2026, 7, 31))
    assert cal.decade_length(2026, 21) == 11
    with pytest.raises(ValueError):
        cal.decade_bounds(2026, 0)


def test_vector_decades_match_scalar_and_cover_year():
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(366)]
    vector = cal.decade_indices(np.array(days, dtype="datetime64[D]"))
    assert vector.tolist() == [cal.decade_index(d) for d in days]
    assert sorted(set(vector.tolist())) == list(range(1, 37))


# ---------------------------------------------------------------- М1


def _frame(n=40, start="2020-01-01"):
    index = pd.date_range(start, periods=n, freq="D")
    return pd.DataFrame({c: np.linspace(1.0, 2.0, n) for c in m1.COLUMNS}, index=index)


def test_qc_interpolates_short_gaps_and_flags_long_ones():
    df = _frame()
    df.loc[df.index[5], "tmax"] = -999.0                 # пропуск 1 сутки
    df.loc[df.index[10:16], "precip"] = np.nan           # пропуск 6 суток
    df.loc[df.index[20], "rh"] = 140.0                   # вне диапазона
    clean, norm_filled, report = m1.quality_control(df)

    assert not clean.isna().any().any()
    assert report.missing["tmax"] == 1 and report.interpolated["tmax"] == 1
    expected = (df["tmax"].iloc[4] + df["tmax"].iloc[6]) / 2
    assert clean["tmax"].iloc[5] == pytest.approx(expected)
    assert report.climatology["precip"] == 6             # длиннее 3 суток — норма, с пометкой
    assert norm_filled["precip"].sum() == 6
    assert report.out_of_range["rh"] == 1
    assert not report.is_clean


def test_altitude_correction_and_gdd():
    # поле на 500 м выше ячейки -> на 3,25 °C холоднее
    assert m1.altitude_correction(20.0, 1200.0, 700.0) == pytest.approx(16.75)
    gdd = m1.gdd_daily(np.array([30.0, 12.0]), np.array([20.0, 4.0]), 10.0)
    assert gdd.tolist() == [15.0, 0.0]


def test_frost_dates():
    dates = np.arange("2021-01-01", "2022-01-01", dtype="datetime64[D]")
    tmin = np.full(dates.size, 5.0)
    tmin[80] = -1.0     # 22 марта
    tmin[300] = -3.0    # 28 октября
    frost = m1.frost_dates(dates, tmin)[2021]
    assert frost == {"last_spring_frost": "2021-03-22", "first_autumn_frost": "2021-10-28"}


# ---------------------------------------------------------------- М2: эталон FAO-56


def test_et0_penman_monteith_fao56_example_18():
    """FAO-56, пример 18: Брюссель, 6 июля. Приёмка ТЗ: расхождение ≤ 0,1 мм/сут."""
    tmax, tmin, u2, rs = 21.5, 12.3, 2.078, 22.07
    lat, z, doy = 50.8, 100.0, 187
    # e_a по RHmax = 84 %, RHmin = 63 %
    ea = (m2.saturation_vapour_pressure(tmin) * 0.84
          + m2.saturation_vapour_pressure(tmax) * 0.63) / 2

    assert float(ea) == pytest.approx(1.409, abs=0.002)
    assert float(m2.atmospheric_pressure(z)) == pytest.approx(100.1, abs=0.05)
    assert float(m2.psychrometric_constant(z)) == pytest.approx(0.0666, abs=0.0002)
    assert float(m2.vapour_pressure_slope((tmax + tmin) / 2)) == pytest.approx(0.122, abs=0.001)
    ra = m2.extraterrestrial_radiation(lat, doy)
    assert float(ra) == pytest.approx(41.09, abs=0.05)
    rso = m2.clear_sky_radiation(ra, z)
    assert float(rso) == pytest.approx(30.90, abs=0.05)
    assert float(m2.net_longwave_radiation(tmax, tmin, ea, rs, rso)) == pytest.approx(3.71,
                                                                                    abs=0.03)
    assert float(m2.net_radiation(tmax, tmin, ea, rs, lat, z, doy)) == pytest.approx(13.28,
                                                                                    abs=0.05)
    et0 = m2.et0_penman_monteith(tmax, tmin, ea, u2, rs, lat, z, doy)
    assert float(et0) == pytest.approx(3.9, abs=0.1)
    assert float(et0) == pytest.approx(3.88, abs=0.02)


def test_et0_hargreaves_fao56_example_20():
    """FAO-56, пример 20: Лион, 15 июля -> 5,0 мм/сут."""
    et0 = m2.et0_hargreaves(26.6, 14.8, 45.72, 196)
    assert float(et0) == pytest.approx(5.0, abs=0.1)


def test_et0_is_vectorised_and_non_negative():
    n = 5
    et0 = m2.et0_penman_monteith(np.full(n, -20.0), np.full(n, -30.0), np.full(n, 0.03),
                                 np.full(n, 1.0), np.full(n, 0.5), 42.9, 700.0,
                                 np.arange(1, n + 1))
    assert et0.shape == (n,) and (et0 >= 0).all()


def test_vapour_pressure_fallback_from_rh():
    ea = m2.actual_vapour_pressure(rh_mean=50.0, tmax=30.0, tmin=20.0)
    es = (m2.saturation_vapour_pressure(30.0) + m2.saturation_vapour_pressure(20.0)) / 2
    assert float(ea) == pytest.approx(float(es) / 2)


# ---------------------------------------------------------------- М3


def test_kc_curve_is_piecewise_linear():
    kc = m3.kc_curve((30, 40, 50, 30), 0.3, 1.2, 0.6)
    assert kc.size == 150
    assert kc[0] == kc[29] == 0.3                       # начальная стадия
    assert kc[69] == pytest.approx(1.2)                 # конец стадии развития
    assert kc[49] == pytest.approx(0.3 + 0.5 * 0.9)     # середина развития
    assert kc[119] == pytest.approx(1.2)                # середина сезона
    assert kc[-1] == pytest.approx(0.6)                 # конец сезона
    assert np.all(np.diff(kc[30:70]) > 0) and np.all(np.diff(kc[120:]) < 0)


def test_kc_climate_adjustment_fao56_eq62():
    # стандартные условия (u2 = 2 м/с, RHmin = 45 %) — без поправки
    assert m3.adjust_kc_for_climate(1.2, 2.0, 45.0, 2.0) == pytest.approx(1.2)
    # сухо и ветрено -> Kc выше
    assert m3.adjust_kc_for_climate(1.2, 4.0, 20.0, 2.0) > 1.2
    expected = 1.2 + (0.04 * 2 - 0.004 * (20 - 45)) * (2.0 / 3.0) ** 0.3
    assert m3.adjust_kc_for_climate(1.2, 4.0, 20.0, 2.0) == pytest.approx(expected)


def test_stage_lengths_shrink_in_hot_year():
    stage_days = (30, 40, 50, 30)
    normal = m3.stage_lengths_from_gdd(np.full(220, 10.0), stage_days, 1500.0)
    hot = m3.stage_lengths_from_gdd(np.full(220, 13.0), stage_days, 1500.0)
    assert normal == stage_days                 # 10 GDD/сут × 150 сут = 1500
    assert sum(hot) < sum(normal)
    assert all(h <= n for h, n in zip(hot, normal, strict=True))


def test_root_depth_grows_during_development_only():
    zr = m3.root_depth_curve((10, 20, 30, 10), 1.2)
    assert zr[0] == zr[9] == 0.15
    assert zr[29] == pytest.approx(1.2) and zr[-1] == 1.2
    assert np.all(np.diff(zr) >= 0)
    assert np.all(m3.root_depth_curve((10, 20, 30, 10), 1.5, perennial=True) == 1.5)
