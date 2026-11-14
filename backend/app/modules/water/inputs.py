"""Входы расчёта воды: приведение чужих объектов к неизменяемым структурам.

Общие схемы Farm / Field / Crop / Scenario принадлежат модулю farms. Чтобы не зависеть
от их точного класса, simulate_field принимает ЛЮБОЙ объект (Pydantic, ORM, dict) и читает
из него атрибуты по именам из раздела 7.1 ТЗ. Что именно читается — см. from_any ниже
и README.md модуля.

Структуры заморожены и хешируемы — по ним кэшируется расчёт.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any


def pick(obj: Any, *names: str, default: Any = None) -> Any:
    """Первое непустое значение среди атрибутов/ключей names."""
    if obj is None:
        return default
    for name in names:
        value = obj.get(name) if isinstance(obj, Mapping) else getattr(obj, name, None)
        if value is not None:
            return value
    return default


def _plain(value: Any) -> Any:
    """Enum -> его значение."""
    return getattr(value, "value", value)


def _float(value: Any) -> float | None:
    return None if value is None else float(value)


def _month_day(value: Any, default: tuple[int, int]) -> tuple[int, int]:
    """'04-01' | date | (4, 1) -> (месяц, день)."""
    if value is None:
        return default
    if isinstance(value, date):
        return value.month, value.day
    if isinstance(value, str):
        parts = value.split("-")
        return int(parts[-2]), int(parts[-1])
    month, day = value
    return int(month), int(day)


def _lat_lon(obj: Any) -> tuple[float | None, float | None]:
    """Координаты поля: lat/lon, точка GeoJSON или центр контура."""
    lat, lon = pick(obj, "lat", "latitude"), pick(obj, "lon", "lng", "longitude")
    if lat is not None and lon is not None:
        return float(lat), float(lon)
    for name in ("location", "location_geojson", "geometry", "geometry_geojson"):
        geo = pick(obj, name)
        if geo is None:
            continue
        if isinstance(geo, str):
            try:
                geo = json.loads(geo)
            except ValueError:
                continue
        if hasattr(geo, "model_dump"):          # Pydantic Point / Polygon модуля farms
            geo = geo.model_dump()
        if not isinstance(geo, Mapping):
            continue
        if "lat" in geo and ("lon" in geo or "lng" in geo):
            return float(geo["lat"]), float(geo.get("lon", geo.get("lng")))
        coords = geo.get("coordinates")
        if geo.get("type") == "Point" and coords:
            return float(coords[1]), float(coords[0])
        if geo.get("type") == "Polygon" and coords:
            ring = coords[0][:-1] or coords[0]
            return (sum(p[1] for p in ring) / len(ring), sum(p[0] for p in ring) / len(ring))
    return None, None


@dataclass(frozen=True)
class WaterInput:
    """Очередь полива и лимит (WaterRight, раздел 7.1). Всё — на водовыпуске хозяйства."""

    turn_interval_days: int | None = None     # очередь раз в N дней
    turn_hours: float | None = None           # часов воды за одну очередь
    flow_l_s: float | None = None             # расход на водовыпуске
    share: float = 1.0                        # доля очереди, идущая на это поле
    limit_m3: float | None = None             # сезонный лимит (если нет часов на очередь)
    season_start: tuple[int, int] = (4, 1)    # начало поливного сезона (месяц, день)
    season_end: tuple[int, int] = (9, 30)
    turn_offset_days: int = 0                 # сдвиг первой очереди от начала сезона
    reliability: float | tuple[float, ...] | None = None   # 0..1 или 36 значений по декадам
    failure_months: tuple[int, ...] = ()      # «месяцы срывов» (UC-1)
    failure_reliability: float = 0.5          # надёжность в месяцы срывов
    conveyance_efficiency: float | None = None  # η_conv канала

    @property
    def is_known(self) -> bool:
        has_turn = self.turn_hours is not None and self.flow_l_s is not None
        return self.turn_interval_days is not None and (has_turn or self.limit_m3 is not None)

    @classmethod
    def from_any(cls, obj: Any) -> "WaterInput":
        if isinstance(obj, cls):
            return obj
        if obj is None:
            return cls()
        reliability = pick(obj, "reliability")
        if isinstance(reliability, (list, tuple)):
            reliability = tuple(float(x) for x in reliability)
        elif reliability is not None:
            reliability = float(reliability)
        interval = pick(obj, "turn_interval_days", "interval_days")
        flow = _float(pick(obj, "flow_l_s", "flow"))
        limit_m3 = _float(pick(obj, "limit_m3"))
        # limit_hours — сезонное право в часах (НЕ часы одной очереди): переводим в объём
        limit_hours = _float(pick(obj, "limit_hours"))
        if limit_m3 is None and limit_hours is not None and flow is not None:
            limit_m3 = limit_hours * 3.6 * flow
        return cls(
            turn_interval_days=None if interval is None else int(interval),
            turn_hours=_float(pick(obj, "turn_hours", "hours")),
            flow_l_s=flow,
            share=float(pick(obj, "turn_share", "share", default=1.0)),
            limit_m3=limit_m3,
            season_start=_month_day(pick(obj, "season_start", "irrigation_start"), (4, 1)),
            season_end=_month_day(pick(obj, "season_end", "irrigation_end"), (9, 30)),
            turn_offset_days=int(pick(obj, "turn_offset_days", default=0)),
            reliability=reliability,
            failure_months=tuple(int(m) for m in pick(obj, "failure_months", default=())
                                 or ()),
            failure_reliability=float(pick(obj, "failure_reliability", default=0.5)),
            conveyance_efficiency=_float(pick(obj, "conveyance_efficiency", "eta_conv")),
        )


@dataclass(frozen=True)
class FieldInput:
    id: str
    name: str
    area_ha: float
    lat: float | None = None
    lon: float | None = None
    elevation_m: float | None = None
    slope_deg: float | None = None
    soil_type: str | None = None
    taw_mm_per_m: float | None = None
    irrigation_method: str = "furrow"
    eta_field: float | None = None                 # измеренный КПД полива на поле
    initial_depletion_fraction: float = 0.5        # начальное D_r = доля × TAW (8.4)
    water: WaterInput = WaterInput()
    # источники значений: (("taw_mm_per_m", "measured"), ...)
    sources: tuple[tuple[str, str], ...] = ()

    def source_of(self, name: str, default: str = "user_estimate") -> str:
        return dict(self.sources).get(name, default)

    @classmethod
    def from_any(cls, field: Any, water: Any = None) -> "FieldInput":
        if isinstance(field, cls) and water is None:
            return field
        lat, lon = _lat_lon(field)
        water_obj = water if water is not None else pick(field, "water", "water_right")
        if water_obj is None and pick(field, "turn_interval_days") is not None:
            water_obj = field  # параметры очереди лежат прямо в поле
        provenance = pick(field, "provenance", default={}) or {}
        source_map = {
            str(k): str(_plain(pick(v, "source_type", default="user_estimate")))
            for k, v in provenance.items()
        } if isinstance(provenance, Mapping) else {}
        water_source = _plain(pick(water_obj, "source_type"))
        if water_source is not None:
            source_map.setdefault("water", str(water_source))
        sources = tuple(sorted(source_map.items()))
        soil = pick(field, "soil_type")
        return cls(
            id=str(pick(field, "id", default="field")),
            name=str(pick(field, "name", default="")),
            area_ha=float(pick(field, "area_ha")),
            lat=lat,
            lon=lon,
            elevation_m=_float(pick(field, "elevation_m")),
            slope_deg=_float(pick(field, "slope_deg")),
            soil_type=None if soil in (None, "unknown") else str(_plain(soil)),
            taw_mm_per_m=_float(pick(field, "taw_mm_per_m")),
            irrigation_method=str(_plain(pick(field, "irrigation_method", default="furrow"))),
            eta_field=_float(pick(field, "eta_field", "field_efficiency")),
            initial_depletion_fraction=float(
                pick(field, "initial_depletion_fraction", default=0.5)),
            water=WaterInput.from_any(water_obj),
            sources=sources,
        )


@dataclass(frozen=True)
class CropInput:
    """Параметры культуры FAO-56 / FAO-33 (Crop, раздел 7.1)."""

    code: str
    name: str
    kc_ini: float
    kc_mid: float
    kc_end: float
    stage_days: tuple[int, int, int, int]
    root_depth_m: float
    p_depletion: float
    ky: float
    ky_stages: tuple[float, float, float, float] | None = None
    t_base: float = 10.0
    t_min_kill: float | None = None
    gdd_required: float | None = None
    t_crit_heat: float | None = None
    k_heat: float | None = None
    k_frost: float | None = None
    height_m: float | None = None
    is_perennial: bool = False
    yield_potential_t_ha: float | None = None

    @classmethod
    def from_any(cls, crop: Any) -> "CropInput":
        if isinstance(crop, cls):
            return crop
        # урожайность и уточнённые стадии могут лежать в варианте культуры (CropVariant)
        variants = pick(crop, "variants", default=()) or ()
        variant = next((v for v in variants
                        if _plain(pick(v, "maturity_class")) == "mid"), None) or (
            variants[0] if variants else None)
        stages = (pick(crop, "stage_days_override") or pick(variant, "stage_days_override")
                  or pick(crop, "stage_days"))
        if stages is None or len(stages) != 4:
            raise ValueError("stage_days должен содержать 4 стадии: ini, dev, mid, late")
        stage_days = tuple(int(x) for x in stages)
        kc = pick(crop, "kc")                    # допускается тройка (ini, mid, end)
        kc_ini, kc_mid, kc_end = (pick(crop, "kc_ini"), pick(crop, "kc_mid"),
                                  pick(crop, "kc_end"))
        if kc_ini is None and kc is not None and len(kc) == 3:
            kc_ini, kc_mid, kc_end = kc
        for name, value in (("kc_ini", kc_ini), ("kc_mid", kc_mid), ("kc_end", kc_end),
                            ("root_depth_m", pick(crop, "root_depth_m")),
                            ("p_depletion", pick(crop, "p_depletion", "p")),
                            ("ky", pick(crop, "ky"))):
            if value is None:
                raise ValueError(f"у культуры не задан обязательный параметр {name}")
        own_yield = pick(crop, "yield_potential_t_ha", "yield_t_ha")
        ky_stages = pick(crop, "ky_stages")
        if ky_stages is not None:
            ky_stages = tuple(float(x) for x in ky_stages)
            if len(ky_stages) != 4:
                ky_stages = None
        return cls(
            code=str(pick(crop, "code", "id", default="crop")),
            name=str(pick(crop, "name_ru", "name", "name_en", default="")),
            kc_ini=float(kc_ini),
            kc_mid=float(kc_mid),
            kc_end=float(kc_end),
            stage_days=stage_days,
            root_depth_m=float(pick(crop, "root_depth_m")),
            p_depletion=float(pick(crop, "p_depletion", "p")),
            ky=float(pick(crop, "ky")),
            ky_stages=ky_stages,
            t_base=float(pick(crop, "t_base", default=10.0)),
            t_min_kill=_float(pick(crop, "t_min_kill")),
            gdd_required=_float(pick(crop, "gdd_required")),
            t_crit_heat=_float(pick(crop, "t_crit_heat")),
            k_heat=_float(pick(crop, "k_heat")),
            k_frost=_float(pick(crop, "k_frost")),
            height_m=_float(pick(crop, "height_m")),
            is_perennial=bool(pick(crop, "is_perennial", "perennial", default=False)),
            yield_potential_t_ha=_float(
                own_yield if own_yield is not None else pick(variant, "yield_potential_t_ha")),
        )


@dataclass(frozen=True)
class ScenarioInput:
    """Внешние условия (Scenario, раздел 7.1) — только то, что влияет на воду и климат.

    yield_factor и цены сюда не входят: их применяет модуль стратегий.
    """

    water_supply_factor: float = 1.0       # 0,5..1,2
    water_supply_months: tuple[int, ...] = ()  # если задано — фактор только в эти месяцы
    supply_shift_days: int = 0             # −30..+30
    temp_delta_c: float = 0.0              # 0..+3
    precip_factor: float = 1.0             # 0,5..1,3
    climate_year: int | None = None        # сценарий «как 2023 год»
    seed: int = 42                         # срывы очереди (воспроизводимость)

    @classmethod
    def from_any(cls, scenario: Any) -> "ScenarioInput":
        if isinstance(scenario, cls):
            return scenario
        if scenario is None:
            return cls()
        climate_year = pick(scenario, "climate_year")
        if climate_year is None:
            mode = _plain(pick(scenario, "climate_mode"))
            if mode in (None, "historical_year"):
                climate_year = pick(pick(scenario, "climate_params"), "year")
        return cls(
            water_supply_factor=float(pick(scenario, "water_supply_factor", default=1.0)),
            water_supply_months=tuple(
                int(m) for m in pick(scenario, "water_supply_months", "water_months",
                                     default=()) or ()),
            supply_shift_days=int(pick(scenario, "supply_shift_days", default=0)),
            temp_delta_c=float(pick(scenario, "temp_delta_c", default=0.0)),
            precip_factor=float(pick(scenario, "precip_factor", default=1.0)),
            climate_year=None if climate_year is None else int(climate_year),
            seed=int(pick(scenario, "seed", default=42)),
        )
