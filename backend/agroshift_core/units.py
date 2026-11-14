"""Единицы и пересчёты (инвариант 7.2 ТЗ)."""

M3_PER_MM_HA = 10.0          # 1 мм слоя воды на 1 га = 10 м³
SECONDS_PER_HOUR = 3600.0


def mm_to_m3(mm: float, area_ha: float) -> float:
    return mm * M3_PER_MM_HA * area_ha


def m3_to_mm(m3: float, area_ha: float) -> float:
    if area_ha <= 0:
        raise ValueError("area_ha must be > 0")
    return m3 / (M3_PER_MM_HA * area_ha)


def flow_volume_m3(hours: float, flow_l_s: float) -> float:
    """Объём за очередь полива: часы × расход (л/с) -> м³."""
    return hours * SECONDS_PER_HOUR * flow_l_s / 1000.0
