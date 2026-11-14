"""Временный демо-профиль для модуля воды — пока модуль farms не отдаёт get_farm / get_crop.

Нужен, чтобы эндпоинты и экраны воды работали независимо (правило «сначала заглушки»).
Как только появится app.modules.farms.service, данные берутся оттуда (см. sources.py),
а этот файл остаётся только для тестов.

Хозяйство «Асан, Сокулук» — раздел 4.2 и 13.2 ТЗ: 6 га, сад, люцерна, кукуруза,
вода по очереди раз в 7–10 дней, в августе часто срывается.
Параметры культур — FAO-56 (табл. 11, 12, 22) и FAO-33; статус «справочник»,
их должен проверить агроном. Урожайности — оценки.
"""

CROPS: dict[str, dict] = {
    "maize": {
        "code": "maize", "name_ru": "Кукуруза на силос", "name_en": "Maize (silage)",
        "kc_ini": 0.30, "kc_mid": 1.20, "kc_end": 0.60,
        "stage_days": (30, 40, 50, 30),
        "root_depth_m": 1.2, "p_depletion": 0.55,
        "ky": 1.25, "ky_stages": (0.4, 0.4, 1.5, 0.5),
        "t_base": 10.0, "t_min_kill": -2.0,
        "t_crit_heat": 35.0, "k_heat": 0.01,
        "height_m": 2.0, "is_perennial": False,
        "yield_potential_t_ha": 40.0,
        "default_sowing": "05-01",
    },
    "alfalfa": {
        "code": "alfalfa", "name_ru": "Люцерна", "name_en": "Alfalfa",
        "kc_ini": 0.40, "kc_mid": 0.95, "kc_end": 0.90,   # с усреднением укосов
        "stage_days": (10, 30, 130, 25),
        "root_depth_m": 1.5, "p_depletion": 0.55,
        "ky": 1.1, "ky_stages": None,
        "t_base": 5.0, "t_min_kill": None,
        "height_m": 0.7, "is_perennial": True,
        "yield_potential_t_ha": 10.0,
        "default_sowing": "04-01",
    },
    "apple": {
        "code": "apple", "name_ru": "Яблоня", "name_en": "Apple",
        "kc_ini": 0.45, "kc_mid": 0.95, "kc_end": 0.70,   # без задернения
        "stage_days": (20, 70, 90, 30),
        "root_depth_m": 1.5, "p_depletion": 0.50,
        "ky": 1.0, "ky_stages": None,
        "t_base": 5.0, "t_min_kill": -2.2,
        "height_m": 4.0, "is_perennial": True,
        "yield_potential_t_ha": 12.0,
        "default_sowing": "04-01",
    },
}

# Очередь: раз в 8 дней по 12 часов на поле при расходе 60 л/с
# (≈1300 м³/га брутто за полив — обычная норма бороздкового полива)
_WATER = {
    "turn_interval_days": 8,
    "turn_hours": 12.0,
    "flow_l_s": 60.0,
    "share": 1.0,
    "season_end": "10-15",
    "reliability": 0.9,
    "failure_months": (8,),
    "failure_reliability": 0.5,
}


def _rect(lat: float, lon: float, d_lat: float = 0.00127, d_lon: float = 0.00173) -> dict:
    """Прямоугольник ~2 га (≈141 × 141 м) с левым нижним углом в (lat, lon)."""
    ring = [[lon, lat], [lon + d_lon, lat], [lon + d_lon, lat + d_lat], [lon, lat + d_lat],
            [lon, lat]]
    return {"type": "Polygon", "coordinates": [ring]}


FARM: dict = {
    "id": "asan",
    "name": "Асан, Сокулук",
    "district": "Сокулукский район",
    "fields": [
        {
            "id": "asan-orchard", "name": "Сад", "area_ha": 2.0, "crop_code": "apple",
            "geometry": _rect(42.8600, 74.3000), "elevation_m": 740.0,
            "soil_type": "loam", "irrigation_method": "furrow", "water": _WATER,
        },
        {
            "id": "asan-alfalfa", "name": "Люцерна", "area_ha": 2.0, "crop_code": "alfalfa",
            "geometry": _rect(42.8600, 74.3020), "elevation_m": 740.0,
            "soil_type": "loam", "irrigation_method": "furrow", "water": _WATER,
        },
        {
            "id": "asan-maize", "name": "Нижнее", "area_ha": 2.0, "crop_code": "maize",
            "geometry": _rect(42.8585, 74.3010), "elevation_m": 738.0,
            "soil_type": "loam", "irrigation_method": "furrow", "water": _WATER,
        },
    ],
}
