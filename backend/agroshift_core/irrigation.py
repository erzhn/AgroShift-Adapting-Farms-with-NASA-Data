"""М5 — подача воды: брутто -> нетто, очередь полива (раздел 8.5 ТЗ).

Место учёта воды фиксируется явно:
    V_head — голова канала, м³
    V_farm — водовыпуск хозяйства, м³:   V_farm = V_head · η_conv
    I_net  — корневая зона, мм:          I_net = V_farm · η_field / (10 · A)

Очередь полива — события: каждые turn_interval_days хозяйство получает
hours × расход (л/с) воды; очередь срывается с вероятностью 1 − reliability.
"""

import numpy as np

from agroshift_core.units import M3_PER_MM_HA, flow_volume_m3

# Справочные КПД полива на поле η_field (8.5): (минимум, максимум)
FIELD_EFFICIENCY: dict[str, tuple[float, float]] = {
    "furrow": (0.45, 0.60),      # бороздковый
    "flood": (0.45, 0.60),       # напуск
    "sprinkler": (0.70, 0.80),   # дождевание
    "drip": (0.85, 0.95),        # капельный
}
# КПД доставки канала η_conv по умолчанию — «оценка» (8.5)
CONVEYANCE_EFFICIENCY_RANGE = (0.35, 0.70)


def field_efficiency_range(method: str | None) -> tuple[float, float]:
    """Диапазон η_field для способа полива; неизвестный способ считаем бороздковым."""
    return FIELD_EFFICIENCY.get(method or "", FIELD_EFFICIENCY["furrow"])


def default_field_efficiency(method: str | None) -> float:
    lo, hi = field_efficiency_range(method)
    return (lo + hi) / 2.0


def default_conveyance_efficiency() -> float:
    lo, hi = CONVEYANCE_EFFICIENCY_RANGE
    return (lo + hi) / 2.0


def farm_volume_from_head(v_head_m3, eta_conv: float):
    """V_farm = V_head · η_conv."""
    return np.asarray(v_head_m3, dtype=float) * eta_conv


def head_volume_from_farm(v_farm_m3, eta_conv: float):
    """Сколько нужно на голове канала, чтобы на водовыпуск пришло V_farm."""
    return np.asarray(v_farm_m3, dtype=float) / eta_conv


def net_irrigation_mm(v_farm_m3, eta_field: float, area_ha: float):
    """I_net, мм = V_farm · η_field / (10 · A)."""
    if area_ha <= 0:
        raise ValueError("area_ha must be > 0")
    return np.asarray(v_farm_m3, dtype=float) * eta_field / (M3_PER_MM_HA * area_ha)


def gross_volume_m3(net_mm, eta_field: float, area_ha: float):
    """Объём на водовыпуске, нужный чтобы до корней дошло net_mm."""
    return np.asarray(net_mm, dtype=float) * M3_PER_MM_HA * area_ha / eta_field


def turn_volume_m3(hours: float, flow_l_s: float) -> float:
    """Объём одной очереди на водовыпуске: часы × расход."""
    return flow_volume_m3(hours, flow_l_s)


def turn_offsets(first_day: int, last_day: int, interval_days: int) -> np.ndarray:
    """Дни очередей (смещения от начала расчётного ряда) с шагом interval_days."""
    if interval_days <= 0 or last_day < first_day:
        return np.array([], dtype=int)
    return np.arange(first_day, last_day + 1, interval_days, dtype=int)


def failed_turns(n_turns: int, reliability, seed: int, year: int) -> np.ndarray:
    """Какие очереди сорваны: вероятность срыва = 1 − reliability (8.5).

    Детерминировано по (seed, year): одно и то же хозяйство в один и тот же год теряет
    одни и те же очереди при любой культуре и стратегии (common random numbers, М10).
    reliability — число или массив длины n_turns.
    """
    if n_turns <= 0:
        return np.array([], dtype=bool)
    rng = np.random.default_rng([abs(int(seed)), abs(int(year))])
    draws = rng.random(n_turns)
    return draws > np.broadcast_to(np.asarray(reliability, dtype=float), (n_turns,))


def loss_per_m3(ky: float, price_som_t: float, yield_t_ha: float, etc_mm: float) -> float:
    """«Убыток от недополива» на 1 м³ — приоритет поля при дележе воды внутри хозяйства:
    Ky × цена × урожайность / ETc (8.5). Чем больше, тем раньше поле получает воду."""
    if etc_mm <= 0:
        return 0.0
    return ky * price_som_t * yield_t_ha / (etc_mm * M3_PER_MM_HA)
