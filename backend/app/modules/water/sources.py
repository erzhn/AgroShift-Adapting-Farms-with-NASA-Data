"""Откуда модуль воды берёт поле, культуру, очередь полива и сценарий.

Единственное место стыка с чужими модулями (внутренние контракты):
    farms.service.get_farm(farm_id) -> Farm     поля, сезоны, водные права (очередь)
    farms.service.get_crop(crop_id) -> Crop     Kc, стадии, Ky, варианты с урожайностью
    farms.service.list_scenario_presets()       готовые сценарии

Если модуля farms или базы нет, эндпоинты воды работают на demo_data
(правило «сначала заглушки»): поля asan-maize, asan-alfalfa, asan-orchard.
"""

import importlib
import logging
import time
from dataclasses import dataclass, replace
from datetime import date
from typing import Any
from uuid import UUID

from app.core.errors import NotFoundError, ProblemError
from app.modules.water import demo_data
from app.modules.water.inputs import CropInput, _month_day, _plain, pick

log = logging.getLogger(__name__)

FARM_CACHE_TTL_S = 30.0   # simulate_field зовут сотни раз подряд — не ходим в БД каждый раз
_farm_cache: dict[str, tuple[float, Any]] = {}


@dataclass(frozen=True)
class FieldContext:
    field: Any                 # объект поля (любой: dict, Pydantic, ORM)
    crop: Any                  # объект культуры
    sowing: tuple[int, int]    # (месяц, день) сева / начала вегетации
    farm_id: str | None
    farm_name: str | None
    source: str                # "farms" | "demo"
    water: Any = None          # очередь полива, если её нет в самом поле


def clear_cache() -> None:
    _farm_cache.clear()


def _optional(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name and module_name.startswith(exc.name):
            return None
        raise


def _farms():
    return _optional("app.modules.farms.service")


def _get_farm(farm_id: Any) -> Any | None:
    """Хозяйство от модуля farms с коротким кэшем. None — модуля, базы или хозяйства нет."""
    farms = _farms()
    if farms is None or not hasattr(farms, "get_farm"):
        return None
    key = str(farm_id)
    now = time.monotonic()
    cached = _farm_cache.get(key)
    if cached and now - cached[0] < FARM_CACHE_TTL_S:
        return cached[1]
    try:
        farm = farms.get_farm(key)
    except Exception as exc:  # noqa: BLE001 — нет базы или хозяйства: считаем без него
        log.warning("farms.get_farm(%s) недоступен: %r", key, exc)
        farm = None
    _farm_cache[key] = (now, farm)
    return farm


def _water_from_farm(farm: Any, field: Any) -> dict | None:
    """Очередь полива поля из водных прав хозяйства (WaterRight).

    Очередь выдаётся хозяйству целиком; поле получает долю по площади среди поливных
    полей (упрощение жадного правила М5 — см. README модуля).
    """
    rights = list(pick(farm, "water_rights", default=()) or ())
    if not rights:
        return None
    canal_id = pick(field, "canal_id")
    same_canal = [r for r in rights
                  if canal_id is not None and str(pick(r, "canal_id")) == str(canal_id)]
    right = max(same_canal or rights, key=lambda r: pick(r, "season", default=0))

    area = float(pick(field, "area_ha"))
    irrigated = sum(
        float(pick(f, "area_ha", default=0.0))
        for f in pick(farm, "fields", default=()) or ()
        if _plain(pick(f, "irrigation_method", default="furrow")) != "none"
    )
    return {
        "turn_interval_days": pick(right, "turn_interval_days"),
        "turn_hours": pick(right, "turn_hours"),
        "flow_l_s": pick(right, "flow_l_s"),
        "limit_m3": pick(right, "limit_m3"),
        "limit_hours": pick(right, "limit_hours"),
        "failure_months": pick(right, "failure_months"),
        "share": min(1.0, area / irrigated) if irrigated > 0 else 1.0,
        "source_type": pick(right, "source_type"),
    }


def farm_water_for(field: Any) -> dict | None:
    """Очередь для поля, в котором её нет: ищем водные права его хозяйства."""
    if (pick(field, "water", "water_right") is not None
            or pick(field, "turn_interval_days") is not None):
        return None
    farm_id = pick(field, "farm_id")
    if farm_id is None:
        return None
    farm = _get_farm(farm_id)
    return None if farm is None else _water_from_farm(farm, field)


def _farm_id_of_field(field_id: str) -> str | None:
    """К какому хозяйству относится поле — одна выборка из БД. None — не нашли."""
    try:
        key = UUID(str(field_id))
    except ValueError:
        return None
    try:
        from sqlalchemy import select

        from app import models
        from app.db.session import SessionLocal

        with SessionLocal() as db:
            farm_id = db.scalar(select(models.Field.farm_id).where(models.Field.id == key))
    except Exception as exc:  # noqa: BLE001 — база недоступна: остаётся демо-профиль
        log.warning("не удалось найти поле %s в базе: %r", field_id, exc)
        return None
    return None if farm_id is None else str(farm_id)


def _from_farms(field_id: str) -> FieldContext | None:
    farms = _farms()
    if farms is None or not hasattr(farms, "get_crop"):
        return None
    farm_id = _farm_id_of_field(field_id)
    farm = _get_farm(farm_id) if farm_id is not None else None
    if farm is None:
        return None
    field = next((f for f in pick(farm, "fields", default=()) or ()
                  if str(pick(f, "id")) == str(field_id)), None)
    if field is None:
        return None

    # текущий план поля — основная культура последнего сезона
    seasons = [s for s in pick(field, "seasons", default=()) or ()
               if pick(s, "is_main", default=True)]
    if not seasons:
        raise ProblemError(409, "Conflict", f"У поля {field_id} не задана культура")
    season = max(seasons, key=lambda s: pick(s, "year", default=0))
    raw_crop = farms.get_crop(pick(season, "crop_id"))
    crop = CropInput.from_any(raw_crop)
    variant = next((v for v in pick(raw_crop, "variants", default=()) or ()
                    if str(pick(v, "id")) == str(pick(season, "crop_variant_id"))), None)
    if variant is not None:  # урожайность и стадии — от варианта, посеянного на поле
        override = pick(variant, "stage_days_override")
        crop = replace(
            crop,
            yield_potential_t_ha=float(pick(variant, "yield_potential_t_ha",
                                            default=crop.yield_potential_t_ha)),
            stage_days=tuple(int(x) for x in override) if override else crop.stage_days,
        )
    sowing = _month_day(pick(season, "sowing_date"), (4, 1) if crop.is_perennial else (5, 1))
    return FieldContext(field, crop, sowing, farm_id, pick(farm, "name"), "farms",
                        _water_from_farm(farm, field))


def _from_demo(field_id: str) -> FieldContext:
    for field in demo_data.FARM["fields"]:
        if field["id"] == field_id:
            crop = demo_data.CROPS[field["crop_code"]]
            sowing = _month_day(crop.get("default_sowing"), (5, 1))
            return FieldContext(field, crop, sowing, demo_data.FARM["id"],
                                demo_data.FARM["name"], "demo")
    raise NotFoundError("Поле", field_id)


def get_field_context(field_id: str) -> FieldContext:
    """Поле по id: сначала модуль farms (id из базы), иначе демо-профиль."""
    return _from_farms(field_id) or _from_demo(field_id)


def resolve_scenario(ref: str | None) -> Any:
    """Сценарий по id или коду пресета. Сценарии принадлежат модулю farms."""
    if ref is None or ref in ("", "base"):
        return None
    farms = _farms()
    try:
        getter = getattr(farms, "get_scenario", None)
        if getter is not None:
            scenario = getter(ref)
            if scenario is not None:
                return scenario
        lister = getattr(farms, "list_scenario_presets", None)
        for scenario in (lister() if lister is not None else ()):
            if ref in (str(pick(scenario, "id")), pick(scenario, "preset_code")):
                return scenario
    except ProblemError:
        raise
    except Exception as exc:  # noqa: BLE001 — база недоступна
        log.warning("не удалось получить сценарий %s: %r", ref, exc)
    raise NotFoundError("Сценарий", ref)


def resolve_strategy_crop(strategy_ref: str | None, field_id: str, year: int) -> Any:
    """Культура и срок сева поля по стратегии (модуль стратегий). None — текущий план."""
    if strategy_ref is None or strategy_ref in ("", "current", "user"):
        return None
    for module_name in ("app.modules.strategies.service", "app.services.strategies"):
        getter = getattr(_optional(module_name), "get_field_plan", None)
        if getter is not None:
            plan = getter(strategy_ref, field_id, year)
            if plan is not None:
                return plan
    raise NotFoundError("Стратегия", strategy_ref)


def sowing_date(sowing: tuple[int, int], year: int) -> date:
    month, day = sowing
    if (month, day) == (2, 29):
        day = 28
    return date(year, month, day)
