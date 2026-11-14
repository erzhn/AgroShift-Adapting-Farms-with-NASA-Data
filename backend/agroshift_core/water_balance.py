"""М4 — суточный водный баланс корневой зоны (раздел 8.4 ТЗ).

Состояние — истощение корневой зоны D_r, мм (0 = полная влагоёмкость, TAW = увядание):

    D_r,d = D_r,d−1 − (P_d − RO_d) − I_net,d + ET_a,d + DP_d
    TAW = 1000·(θ_FC − θ_WP)·Z_r,   RAW = p·TAW
    K_s = 1 при D_r ≤ RAW, иначе (TAW − D_r) / ((1 − p)·TAW);   ET_a = K_s·ET_c

K_s считается по истощению на конец предыдущих суток (как в FAO-56 и в примере 15.1).
Дождь и полив идут в один баланс; сток и глубокая фильтрация считаются явно.
"""

from dataclasses import dataclass

import numpy as np

# Доступная влага почвы, мм на 1 м глубины = 1000·(θ_FC − θ_WP). FAO-56, табл. 19 (середины)
TAW_MM_PER_M: dict[str, float] = {
    "sand": 80.0,
    "sandy_loam": 130.0,   # супесь
    "loam": 155.0,         # суглинок
    "silt_loam": 160.0,
    "serozem": 160.0,      # серозём — пылеватый суглинок
    "clay_loam": 155.0,
    "clay": 160.0,
}
TAW_MM_PER_M_DEFAULT = 140.0   # если почва неизвестна (как в примере 15.1)

# Curve Number SCS для пропашных культур по типу почвы (справочные значения)
CURVE_NUMBER: dict[str, float] = {
    "sand": 67.0,
    "sandy_loam": 72.0,
    "loam": 78.0,
    "silt_loam": 79.0,
    "serozem": 79.0,
    "clay_loam": 85.0,
    "clay": 89.0,
}
CURVE_NUMBER_DEFAULT = 78.0


def curve_number(soil_type: str | None, slope_deg: float | None = None) -> float:
    """CN по типу почвы и уклону (8.4). Уклон круче 3° и 8° повышает сток."""
    cn = CURVE_NUMBER.get(soil_type or "", CURVE_NUMBER_DEFAULT)
    if slope_deg is not None:
        if slope_deg > 8.0:
            cn += 6.0
        elif slope_deg > 3.0:
            cn += 3.0
    return min(cn, 95.0)


def scs_runoff(precip, cn: float):
    """Сток RO, мм: (P − 0,2S)² / (P + 0,8S) при P > 0,2S; S = 25400/CN − 254."""
    p = np.asarray(precip, dtype=float)
    s = 25400.0 / cn - 254.0
    excess = np.maximum(p - 0.2 * s, 0.0)
    return np.where(p > 0.2 * s, excess ** 2 / (p + 0.8 * s), 0.0)


def total_available_water(taw_mm_per_m: float, root_depth_m):
    """TAW, мм = 1000·(θ_FC − θ_WP)·Z_r."""
    return taw_mm_per_m * np.asarray(root_depth_m, dtype=float)


def stress_coefficient(dr: float, taw: float, p: float) -> float:
    """K_s — коэффициент водного стресса, 0..1."""
    if taw <= 0:
        return 0.0
    raw = p * taw
    if dr <= raw:
        return 1.0
    return max(0.0, (taw - dr) / ((1.0 - p) * taw))


@dataclass(frozen=True)
class BalanceResult:
    """Суточные ряды баланса, мм."""

    dr: np.ndarray            # истощение на конец суток
    ks: np.ndarray            # коэффициент стресса
    eta: np.ndarray           # фактическая эвапотранспирация
    irrigation: np.ndarray    # принятый полив нетто
    runoff: np.ndarray        # сток
    dp: np.ndarray            # глубокая фильтрация (потерянная вода)
    dp_rain: np.ndarray       # часть фильтрации, вызванная дождём
    taw: np.ndarray
    raw: np.ndarray
    dr0: float                # истощение перед первым днём
    root_gain: float          # влага, добавленная ростом корневой зоны

    def closure_error(self, precip: np.ndarray) -> float:
        """Невязка баланса за период: P + I − ETa − RO − DP + прирост зоны − ΔЗапаса."""
        storage_start = float(self.taw[0]) - self.dr0
        storage_end = float(self.taw[-1] - self.dr[-1])
        inflow = float(np.sum(precip) + self.irrigation.sum() + self.root_gain)
        outflow = float(self.eta.sum() + self.runoff.sum() + self.dp.sum())
        # запас первого дня считаем от TAW первого дня; рост TAW учтён в root_gain
        return inflow - outflow - (storage_end - storage_start)


def simulate_root_zone(
    etc,
    precip,
    taw,
    p: float,
    dr0: float,
    runoff=None,
    irrigation_net=None,
    irrigation_available=None,
    new_soil_depletion: float = 0.5,
) -> BalanceResult:
    """Суточный баланс корневой зоны одного поля.

    etc, precip — мм/сут; taw — число или суточный ряд (растёт вместе с корнями);
    p — доля легкодоступной влаги; dr0 — начальное истощение.

    Полив задаётся одним из двух способов:
      irrigation_net       — фиксированная норма нетто по дням, вносится целиком
                             (избыток уходит в глубокую фильтрацию);
      irrigation_available — сколько воды нетто доступно в день очереди; вносится
                             не больше, чем нужно, чтобы к концу суток D_r = 0
                             (правило М5), то есть с учётом расхода за этот день.

    При таком правиле расчёт монотонен: меньше воды -> D_r не меньше в каждый день
    -> ETa и урожай не больше.

    new_soil_depletion — доля истощения слоя, в который дорастают корни.
    """
    etc = np.asarray(etc, dtype=float)
    precip = np.asarray(precip, dtype=float)
    n = etc.size
    taw_arr = np.broadcast_to(np.asarray(taw, dtype=float), (n,))
    ro = np.zeros(n) if runoff is None else np.asarray(runoff, dtype=float)
    fixed = None if irrigation_net is None else np.asarray(irrigation_net, dtype=float)
    avail = None if irrigation_available is None else np.asarray(irrigation_available,
                                                                 dtype=float)
    if fixed is not None and avail is not None:
        raise ValueError("задайте либо irrigation_net, либо irrigation_available")

    etc_l, p_l, ro_l, taw_l = etc.tolist(), precip.tolist(), ro.tolist(), taw_arr.tolist()
    fixed_l = fixed.tolist() if fixed is not None else None
    avail_l = avail.tolist() if avail is not None else None

    dr_out, ks_out, eta_out = [0.0] * n, [0.0] * n, [0.0] * n
    irr_out, dp_out, dp_rain_out = [0.0] * n, [0.0] * n, [0.0] * n
    one_minus_p = 1.0 - p
    prev = float(dr0)
    prev_taw = taw_l[0] if n else 0.0
    root_gain = 0.0

    for d in range(n):
        taw_d = taw_l[d]
        if taw_d > prev_taw:
            # корни вошли в новый слой: он приносит свою влагу и своё истощение
            growth = taw_d - prev_taw
            prev += new_soil_depletion * growth
            root_gain += (1.0 - new_soil_depletion) * growth
        prev_taw = taw_d

        etc_d = etc_l[d]
        effective_rain = p_l[d] - ro_l[d]
        stress_zone = one_minus_p * taw_d          # TAW − RAW
        if etc_d > stress_zone or stress_zone <= 0.0:
            # Зона стресса тоньше суточной потребности (очень мелкие корни): суточный шаг
            # не разрешает постепенный стресс. Культура берёт, сколько осталось доступной
            # влаги плюс дождь этого дня — иначе истощение ушло бы за TAW.
            eta = min(etc_d, max(taw_d - prev + effective_rain, 0.0))
            ks = eta / etc_d if etc_d > 0.0 else 0.0
        else:
            ks = 1.0 if prev <= p * taw_d else max(0.0, (taw_d - prev) / stress_zone)
            eta = ks * etc_d

        if fixed_l is not None:
            irrigation = fixed_l[d]
        elif avail_l is not None and avail_l[d] > 0.0:
            irrigation = min(avail_l[d], max(0.0, prev - effective_rain + eta))
        else:
            irrigation = 0.0

        after_rain = prev - effective_rain
        current = after_rain - irrigation + eta
        if current < 0.0:
            dp = -current
            current = 0.0
            # сколько фильтрации дал бы один дождь, без полива
            dp_rain = min(dp, max(0.0, -(after_rain + eta)))
        else:
            dp = dp_rain = 0.0
        if current > taw_d:
            current = taw_d

        dr_out[d], ks_out[d], eta_out[d] = current, ks, eta
        irr_out[d], dp_out[d], dp_rain_out[d] = irrigation, dp, dp_rain
        prev = current

    return BalanceResult(
        dr=np.array(dr_out), ks=np.array(ks_out), eta=np.array(eta_out),
        irrigation=np.array(irr_out), runoff=ro.copy(), dp=np.array(dp_out),
        dp_rain=np.array(dp_rain_out), taw=np.array(taw_l), raw=p * np.array(taw_l),
        dr0=float(dr0), root_gain=root_gain,
    )
