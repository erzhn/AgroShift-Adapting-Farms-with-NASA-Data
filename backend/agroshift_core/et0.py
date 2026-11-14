"""М2 — эталонная эвапотранспирация ET0 (раздел 8.2 ТЗ).

Основной метод — FAO-56 Penman–Monteith (Allen et al., 1998), суточный шаг, G = 0.
Резервный — Hargreaves–Samani, когда нет радиации или ветра.

Все функции векторные: принимают числа или массивы NumPy.
Приёмка: пример 18 FAO-56 совпадает с точностью ±0,1 мм/сут (см. тесты).
"""

import numpy as np

SOLAR_CONSTANT = 0.0820        # Gsc, МДж/м²/мин
STEFAN_BOLTZMANN = 4.903e-9    # σ, МДж/К⁴/м²/сут
ALBEDO = 0.23                  # эталонный травостой


def atmospheric_pressure(elevation_m):
    """P, кПа: 101,3·((293 − 0,0065·z)/293)^5,26."""
    return 101.3 * ((293.0 - 0.0065 * np.asarray(elevation_m, dtype=float)) / 293.0) ** 5.26


def psychrometric_constant(elevation_m):
    """γ, кПа/°C: 0,000665·P."""
    return 0.000665 * atmospheric_pressure(elevation_m)


def saturation_vapour_pressure(temp_c):
    """e°(T), кПа: 0,6108·exp(17,27·T/(T + 237,3))."""
    t = np.asarray(temp_c, dtype=float)
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def vapour_pressure_slope(temp_c):
    """Δ, кПа/°C: 4098·e°(T)/(T + 237,3)²."""
    t = np.asarray(temp_c, dtype=float)
    return 4098.0 * saturation_vapour_pressure(t) / (t + 237.3) ** 2


def actual_vapour_pressure(tdew=None, rh_mean=None, tmax=None, tmin=None):
    """e_a, кПа. Основной способ — по точке росы; резерв — по средней влажности RH2M."""
    if tdew is not None:
        return saturation_vapour_pressure(tdew)
    if rh_mean is None or tmax is None or tmin is None:
        raise ValueError("нужна точка росы либо RH и Tmax/Tmin")
    es = (saturation_vapour_pressure(tmax) + saturation_vapour_pressure(tmin)) / 2.0
    return np.asarray(rh_mean, dtype=float) / 100.0 * es


def extraterrestrial_radiation(lat_deg: float, doy):
    """R_a, МДж/м²/сут (FAO-56, ур. 21)."""
    j = np.asarray(doy, dtype=float)
    phi = np.radians(lat_deg)
    dr = 1.0 + 0.033 * np.cos(2.0 * np.pi * j / 365.0)
    delta = 0.409 * np.sin(2.0 * np.pi * j / 365.0 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1.0, 1.0))
    return (24.0 * 60.0 / np.pi) * SOLAR_CONSTANT * dr * (
        ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws)
    )


def clear_sky_radiation(ra, elevation_m):
    """R_so, МДж/м²/сут (FAO-56, ур. 37): (0,75 + 2·10⁻⁵·z)·R_a."""
    return (0.75 + 2e-5 * np.asarray(elevation_m, dtype=float)) * ra


def net_longwave_radiation(tmax, tmin, ea, rs, rso):
    """R_nl, МДж/м²/сут (FAO-56, ур. 39)."""
    tmax_k4 = (np.asarray(tmax, dtype=float) + 273.16) ** 4
    tmin_k4 = (np.asarray(tmin, dtype=float) + 273.16) ** 4
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(np.asarray(rso) > 0, np.asarray(rs) / np.asarray(rso), 1.0)
    ratio = np.clip(ratio, 0.3, 1.0)
    return (STEFAN_BOLTZMANN * (tmax_k4 + tmin_k4) / 2.0
            * (0.34 - 0.14 * np.sqrt(np.asarray(ea, dtype=float)))
            * (1.35 * ratio - 0.35))


def net_radiation(tmax, tmin, ea, rs, lat_deg: float, elevation_m: float, doy):
    """R_n = R_ns − R_nl, R_ns = (1 − 0,23)·R_s."""
    ra = extraterrestrial_radiation(lat_deg, doy)
    rso = clear_sky_radiation(ra, elevation_m)
    rns = (1.0 - ALBEDO) * np.asarray(rs, dtype=float)
    return rns - net_longwave_radiation(tmax, tmin, ea, rs, rso)


def et0_penman_monteith(tmax, tmin, ea, u2, rs, lat_deg: float, elevation_m: float, doy,
                        g: float = 0.0):
    """ET0, мм/сут — FAO-56 Penman–Monteith (ур. 6).

    tmax, tmin — °C; ea — кПа; u2 — м/с на 2 м; rs — МДж/м²/сут;
    lat_deg — широта; elevation_m — высота поля; doy — номер дня года; g — поток тепла в почву.
    """
    tmax = np.asarray(tmax, dtype=float)
    tmin = np.asarray(tmin, dtype=float)
    u2 = np.asarray(u2, dtype=float)
    t = (tmax + tmin) / 2.0
    es = (saturation_vapour_pressure(tmax) + saturation_vapour_pressure(tmin)) / 2.0
    delta = vapour_pressure_slope(t)
    gamma = psychrometric_constant(elevation_m)
    rn = net_radiation(tmax, tmin, ea, rs, lat_deg, elevation_m, doy)
    vpd = np.maximum(es - np.asarray(ea, dtype=float), 0.0)
    numerator = 0.408 * delta * (rn - g) + gamma * 900.0 / (t + 273.0) * u2 * vpd
    denominator = delta + gamma * (1.0 + 0.34 * u2)
    return np.maximum(numerator / denominator, 0.0)


def et0_hargreaves(tmax, tmin, lat_deg: float, doy):
    """ET0, мм/сут — Hargreaves–Samani (резерв, «упрощённый метод»).

    0,0023·R_a·(T + 17,8)·√(Tmax − Tmin), R_a переводится в мм/сут (× 0,408).
    """
    tmax = np.asarray(tmax, dtype=float)
    tmin = np.asarray(tmin, dtype=float)
    t = (tmax + tmin) / 2.0
    ra_mm = 0.408 * extraterrestrial_radiation(lat_deg, doy)
    return np.maximum(0.0023 * ra_mm * (t + 17.8) * np.sqrt(np.maximum(tmax - tmin, 0.0)), 0.0)
