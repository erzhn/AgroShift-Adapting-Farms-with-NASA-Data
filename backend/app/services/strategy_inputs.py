"""Входы модуля «Стратегии и деньги»: хозяйство, культуры, вода по годам.

Единственное место, где модуль стратегий касается чужих модулей (внутренние контракты):

    farms.get_farm(farm_id) -> Farm              (Баяман)
    farms.get_crop(crop_id) -> Crop              (Баяман)
    water.simulate_field(field, crop, sowing_date, scenario, year) -> FieldSeason   (Ислам)
    water.history_years() -> list[int]           (Ислам)

Пока этих функций нет (или они бросают ошибку), работает встроенная ЗАГЛУШКА: демо-хозяйство
«Асан» и упрощённая модель воды на синтетических 30 годах. Заглушка — не данные NASA: ответы
API честно помечают это в `inputs_status`, а числа нужны только для того, чтобы экран и
остальные модули работали до готовности настоящих функций. Имена полей, которые читает
адаптер, описаны в docs/strategies-module.md.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

import numpy as np

from agroshift_core.feed import herd_demand_dm_kg
from agroshift_core.plan_eval import DECADES, CropParams, FarmEcon

log = logging.getLogger(__name__)

FARM_MODULES = ("app.services.farms", "app.modules.farms.service")
WATER_MODULES = ("app.services.water", "app.modules.water.service")

MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _decade_calendar() -> tuple[np.ndarray, np.ndarray]:
    """Номер декады (0..35) для каждого дня невисокосного года и число дней в декаде."""
    day_decade = []
    for month, days in enumerate(MONTH_DAYS):
        for day in range(1, days + 1):
            day_decade.append(month * 3 + min(2, (day - 1) // 10))
    day_decade = np.array(day_decade)
    return day_decade, np.bincount(day_decade, minlength=DECADES).astype(float)


DAY_DECADE, DECADE_DAYS = _decade_calendar()


# ----------------------------------------------------------------------------- модель входов


@dataclass(frozen=True)
class Scn:
    """Сценарий условий. Базовый сценарий — значения по умолчанию."""

    water_supply_factor: float = 1.0
    supply_shift_days: float = 0.0
    temp_delta_c: float = 0.0
    precip_factor: float = 1.0
    water_months: tuple[int, ...] = ()  # месяцы 1..12, к которым относится множитель подачи
    price_factor: float = 1.0
    price_factors: tuple[tuple[str, float], ...] = ()
    feed_price_factor: float = 1.0
    payment_delay_days: float = 0.0
    yield_factor: float = 1.0

    def water_key(self) -> tuple:
        """Часть сценария, от которой зависит модель воды (ключ кэша)."""
        return (
            round(self.water_supply_factor, 4),
            round(self.supply_shift_days, 2),
            round(self.temp_delta_c, 3),
            round(self.precip_factor, 4),
            self.water_months,
        )


@dataclass(frozen=True)
class CropInfo:
    params: CropParams
    name_ru: str
    name_en: str
    perennial: bool = False  # многолетняя: повтор на поле — норма
    repeat_allowed: bool = True  # можно ли сеять по самой себе (севооборот)
    plantable: bool = True  # можно ли предлагать как новую культуру
    uproot_cost_som_ha: float = 0.0
    sowing_mmdd: tuple[int, int] = (4, 15)
    agro_status: str = "approved"  # approved / experimental
    # параметры только для заглушки воды
    kc: tuple[float, float, float] = (0.4, 1.0, 0.6)
    stage_days: tuple[int, int, int, int] = (25, 35, 40, 30)
    ky: float = 1.0
    raw: Any = None  # объект Crop владельца — уходит в simulate_field как есть


@dataclass(frozen=True)
class FieldInfo:
    id: str
    name: str
    area_ha: float
    crop_id: str  # текущая культура = «Мой вариант»
    raw: Any = None


@dataclass(frozen=True)
class FieldSims:
    """Вода одной пары (поле, культура) по всем годам-выборкам, на 1 га."""

    yield_mult: np.ndarray  # (S,) множитель урожая Ya/Ym
    gross_mm: np.ndarray  # (S, 36) потребность брутто
    deficit_mm: np.ndarray  # (S, 36) дефицит нетто (не дошло до корней)


@dataclass(frozen=True)
class FarmInputs:
    farm_id: str
    name: str
    fields: tuple[FieldInfo, ...]
    crops: dict[str, CropInfo]
    econ: FarmEcon
    years: tuple[int, ...]
    status: dict[str, str]  # {"farm": "stub"|"service", "water": "stub"|"service"}
    warnings: tuple[str, ...] = ()
    _water_fn: Any = field(default=None, repr=False, compare=False)

    def simulate(self, fld: FieldInfo, crop: CropInfo, scn: Scn) -> FieldSims:
        if self._water_fn is not None:
            try:
                return _simulate_external(self._water_fn, fld, crop, scn, self.years)
            except Exception:  # noqa: BLE001 — чужой модуль не должен ронять экран стратегий
                log.exception("water.simulate_field упал — считаю на заглушке")
        return stub_simulate(crop, scn, self.years)


# ----------------------------------------------------------------------------- демо-данные

_Z = (0.0,) * 12


def _months(**by_month: float) -> tuple[float, ...]:
    names = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
    return tuple(float(by_month.get(n, 0.0)) for n in names)


# Все цифры ниже — «оценка» для демо (не статистика): заменяются справочником Баямана.
DEMO_CROPS: dict[str, CropInfo] = {
    "alfalfa": CropInfo(
        CropParams(
            "alfalfa", 10.0, 9_000,
            _months(mar=3_000, may=2_000, jun=5_000, jul=4_000, sep=4_000),
            _months(jun=0.40, jul=0.35, sep=0.25),
            is_feed=True, dm_share=0.85, establish_yield_factor=0.6,
        ),
        "Люцерна", "Alfalfa", perennial=True, sowing_mmdd=(4, 1),
        kc=(0.40, 0.95, 0.90), stage_days=(15, 30, 120, 30), ky=1.1,
    ),
    "corn": CropInfo(
        CropParams(
            "corn", 7.0, 17_000,
            _months(apr=18_000, may=9_000, jun=7_000, jul=4_000, oct=12_000),
            _months(oct=1.0),
        ),
        "Кукуруза", "Maize", sowing_mmdd=(4, 25),
        kc=(0.30, 1.20, 0.60), stage_days=(25, 40, 45, 30), ky=1.25,
    ),
    "wheat": CropInfo(
        CropParams(
            "wheat", 4.5, 18_000,
            _months(mar=12_000, apr=6_000, may=4_000, aug=6_000),
            _months(aug=1.0),
        ),
        "Пшеница", "Wheat", repeat_allowed=False, sowing_mmdd=(3, 25),
        kc=(0.30, 1.15, 0.30), stage_days=(20, 30, 50, 30), ky=1.15,
    ),
    "beans": CropInfo(
        CropParams(
            "beans", 2.2, 75_000,
            _months(apr=4_000, may=16_000, jun=8_000, jul=5_000, sep=7_000),
            _months(sep=1.0),
            max_volume_t=3.0,
        ),
        "Фасоль", "Beans", repeat_allowed=False, sowing_mmdd=(5, 10),
        kc=(0.40, 1.15, 0.35), stage_days=(20, 30, 40, 20), ky=1.15,
    ),
    "apple": CropInfo(
        CropParams(
            "apple", 9.0, 25_000,
            _months(mar=12_000, apr=8_000, may=8_000, jun=8_000, jul=6_000, sep=18_000),
            _months(sep=0.6, oct=0.4),
        ),
        "Яблоня (старый сад)", "Apple (old orchard)", perennial=True, plantable=False,
        uproot_cost_som_ha=60_000, sowing_mmdd=(4, 1),
        kc=(0.50, 1.00, 0.75), stage_days=(30, 50, 90, 30), ky=1.0,
    ),
}

DEMO_FIELDS = (
    FieldInfo("f1", "Сад", 2.0, "apple"),
    FieldInfo("f2", "Поле у канала", 2.0, "alfalfa"),
    FieldInfo("f3", "Дальнее поле", 2.0, "corn"),
)

DEMO_HERD = {"head_count": 8, "dmi_kg_day": 14.0}
DEMO_GRAZING = _months(apr=0.3, may=0.6, jun=0.6, jul=0.6, aug=0.6, sep=0.6, oct=0.3)


def demo_econ() -> FarmEcon:
    demand = herd_demand_dm_kg(DEMO_HERD["head_count"], DEMO_HERD["dmi_kg_day"], DEMO_GRAZING)
    return FarmEcon(
        opening_cash_som=180_000,
        reserve_som=30_000,
        family_by_month=(40_000,) * 12,
        debt_by_month=_Z,
        milk_income_by_month=_months(
            jan=45_000, feb=50_000, mar=60_000, apr=70_000, may=80_000, jun=80_000,
            jul=75_000, aug=70_000, sep=60_000, oct=50_000, nov=45_000, dec=40_000,
        ),
        herd_cost_by_month=(12_000,) * 12,
        feed_demand_dm_kg=tuple(float(x) for x in demand),
        # запас на 1 января: корм до первого укоса в июне
        feed_opening_stock_dm_kg=float(demand[:5].sum()),
        feed_price_som_t=10_000,
        feed_dm_share=0.85,
        water_fee_som_m3=0.0,
        payment_delay_days=45,
    )


STUB_YEARS = tuple(range(1996, 2026))

# Заглушка климата и подачи (Чуйская долина, порядок величин), по месяцам
_ET0_MM_DAY = (0.6, 1.0, 2.0, 3.5, 5.0, 6.2, 6.8, 6.0, 4.2, 2.4, 1.1, 0.6)
_PRECIP_MM = (25, 30, 45, 65, 60, 35, 18, 12, 18, 35, 38, 30)
_SUPPLY_GROSS_MM_DECADE = (0, 0, 0, 60, 85, 105, 105, 95, 60, 0, 0, 0)
_ETA_FIELD = 0.55  # бороздковый полив
_BUCKET_MM = 90.0  # легкодоступная влага корневой зоны


def stub_year_anomalies(years: tuple[int, ...]) -> dict[str, np.ndarray]:
    """Синтетическая погода года: ΔT, множитель осадков, множитель подачи. Детерминировано."""
    d_t, precip, supply = [], [], []
    for year in years:
        rng = np.random.default_rng(np.random.SeedSequence([20261115, year]))
        z = rng.standard_normal(3)
        t = 0.8 * z[0] + 0.03 * (year - 2010)
        d_t.append(t)
        precip.append(float(np.exp(0.25 * z[1] - 0.12 * t)))  # жаркий год чаще сухой
        supply.append(float(np.clip(1.0 + 0.10 * z[2] - 0.06 * t, 0.6, 1.2)))
    return {"temp": np.array(d_t), "precip": np.array(precip), "supply": np.array(supply)}


def _kc_by_decade(crop: CropInfo) -> np.ndarray:
    start = date(2025, *crop.sowing_mmdd).timetuple().tm_yday - 1
    ini, dev, mid, late = crop.stage_days
    k_ini, k_mid, k_end = crop.kc
    daily = np.zeros(365)
    stage = np.concatenate([
        np.full(ini, k_ini),
        np.linspace(k_ini, k_mid, dev, endpoint=False),
        np.full(mid, k_mid),
        np.linspace(k_mid, k_end, late),
    ])
    end = min(365, start + stage.size)
    daily[start:end] = stage[: end - start]
    return np.bincount(DAY_DECADE, weights=daily, minlength=DECADES) / DECADE_DAYS


def stub_simulate(crop: CropInfo, scn: Scn, years: tuple[int, ...]) -> FieldSims:
    """Упрощённый декадный баланс «ведро» на 1 га. ЗАГЛУШКА до simulate_field Ислама."""
    anomalies = stub_year_anomalies(years)
    n = len(years)
    month = np.arange(DECADES) // 3
    kc = _kc_by_decade(crop)
    d_t = anomalies["temp"] + scn.temp_delta_c
    et0 = np.array(_ET0_MM_DAY)[month] * DECADE_DAYS
    etc = kc[None, :] * et0[None, :] * (1.0 + 0.035 * d_t)[:, None]
    month_days = np.array(MONTH_DAYS, dtype=float)[month]
    p_eff = (
        0.75 * np.array(_PRECIP_MM, dtype=float)[month] * DECADE_DAYS / month_days
    )[None, :] * (anomalies["precip"] * scn.precip_factor)[:, None]

    supply = np.array(_SUPPLY_GROSS_MM_DECADE, dtype=float)[month]
    if scn.supply_shift_days:
        pos = np.arange(DECADES) - scn.supply_shift_days / 10.0
        supply = np.interp(pos, np.arange(DECADES), supply, left=0.0, right=0.0)
    factor = np.full(DECADES, scn.water_supply_factor)
    if scn.water_months:
        factor = np.where(np.isin(month + 1, scn.water_months), scn.water_supply_factor, 1.0)
    supply_net = (supply * factor)[None, :] * anomalies["supply"][:, None] * _ETA_FIELD

    store = np.full(n, _BUCKET_MM)
    gross = np.zeros((n, DECADES))
    deficit = np.zeros((n, DECADES))
    for d in range(DECADES):
        if kc[d] <= 0:
            store = np.minimum(_BUCKET_MM, store + p_eff[:, d])
            continue
        want = np.maximum(0.0, etc[:, d] - p_eff[:, d] + (_BUCKET_MM - store))
        irrigation = np.minimum(want, supply_net[:, d])
        store = np.minimum(_BUCKET_MM, store + p_eff[:, d] + irrigation)
        eta = np.minimum(etc[:, d], store)
        store = store - eta
        gross[:, d] = np.maximum(0.0, etc[:, d] - p_eff[:, d]) / _ETA_FIELD  # потребность
        deficit[:, d] = etc[:, d] - eta
    season = etc[:, kc > 0].sum(axis=1)
    relative = np.divide(deficit.sum(axis=1), season, out=np.zeros(n), where=season > 0)
    return FieldSims(np.clip(1.0 - crop.ky * relative, 0.0, 1.0), gross, deficit)


def demo_inputs(farm_id: str, warnings: tuple[str, ...] = ()) -> FarmInputs:
    return FarmInputs(
        farm_id=farm_id,
        name="Асан, Сокулук (демо)",
        fields=DEMO_FIELDS,
        crops=DEMO_CROPS,
        econ=demo_econ(),
        years=STUB_YEARS,
        status={"farm": "stub", "water": "stub"},
        warnings=warnings,
    )


# ----------------------------------------------------------------------------- адаптеры


def _find(modules: tuple[str, ...], name: str) -> Any:
    for module_name in modules:
        try:
            fn = getattr(importlib.import_module(module_name), name, None)
        except ImportError:
            continue
        if callable(fn):
            return fn
    return None


def _pick(obj: Any, *names: str, default: Any = None) -> Any:
    """Значение первого найденного атрибута/ключа. None считается «нет значения»."""
    for name in names:
        value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
        if value is not None:
            return value
    return default


def _twelve(value: Any, fallback: tuple[float, ...]) -> tuple[float, ...]:
    if value is None:
        return fallback
    if isinstance(value, (int, float)):
        return (float(value),) * 12
    values = tuple(float(v) for v in value)
    return values if len(values) == 12 else fallback


def _crop_from_service(raw: Any, base: CropInfo | None) -> CropInfo:
    """Crop владельца → CropInfo. Чего нет в справочнике — берётся из демо-оценки `base`."""
    crop_id = str(_pick(raw, "id", "crop_id", "code"))
    b = base or DEMO_CROPS["corn"]
    p = b.params
    cost = _pick(raw, "cost_som_ha_by_month", "costs_by_month")
    if cost is None and _pick(raw, "cost_som_ha", "cost") is not None:
        total = float(_pick(raw, "cost_som_ha", "cost"))
        scale = total / max(1.0, sum(p.cost_som_ha_by_month))
        cost = tuple(c * scale for c in p.cost_som_ha_by_month)
    price = _pick(raw, "price_som_t", "price")
    if price is None and _pick(raw, "price_som_kg") is not None:
        price = float(_pick(raw, "price_som_kg")) * 1000.0
    params = CropParams(
        crop_id=crop_id,
        yield_t_ha=float(_pick(raw, "yield_t_ha", "yield_potential_t_ha", default=p.yield_t_ha)),
        price_som_t=None if price is None else float(price),  # пропуск ≠ ноль
        cost_som_ha_by_month=_twelve(cost, p.cost_som_ha_by_month),
        harvest_shares=_twelve(_pick(raw, "harvest_shares"), p.harvest_shares),
        is_feed=bool(_pick(raw, "is_feed", default=p.is_feed)),
        dm_share=float(_pick(raw, "dm_share", default=p.dm_share)),
        max_volume_t=_pick(raw, "max_volume_t", default=p.max_volume_t if base else None),
        distress_factor=float(_pick(raw, "distress_factor", default=p.distress_factor)),
        establish_yield_factor=float(
            _pick(raw, "establish_yield_factor", default=p.establish_yield_factor if base else 1.0)
        ),
    )
    sowing = _pick(raw, "sowing_date", "sowing_mmdd")
    if isinstance(sowing, str):
        sowing = date.fromisoformat(sowing)
    mmdd = (sowing.month, sowing.day) if isinstance(sowing, date) else (sowing or b.sowing_mmdd)
    return CropInfo(
        params=params,
        name_ru=str(_pick(raw, "name_ru", "name", default=b.name_ru if base else crop_id)),
        name_en=str(_pick(raw, "name_en", "name", default=b.name_en if base else crop_id)),
        perennial=bool(_pick(raw, "perennial", "is_perennial", default=base.perennial if base
                             else False)),
        repeat_allowed=bool(_pick(raw, "repeat_allowed", default=base.repeat_allowed if base
                                  else True)),
        plantable=bool(_pick(raw, "plantable", default=base.plantable if base else True)),
        uproot_cost_som_ha=float(
            _pick(raw, "uproot_cost_som_ha", default=base.uproot_cost_som_ha if base else 0.0)
        ),
        sowing_mmdd=tuple(mmdd),
        agro_status=str(_pick(raw, "agro_status", "status", default="approved")),
        kc=b.kc, stage_days=b.stage_days, ky=float(_pick(raw, "ky", default=b.ky)),
        raw=raw,
    )


def _farm_from_service(farm_id: str, raw: Any, get_crop: Any) -> FarmInputs:
    """Farm владельца → FarmInputs. Недостающие деньги/скот берутся из демо с пометкой."""
    from app.modules.farms import schemas, service
    from app.modules.farms.strategy_adapter import strategy_inputs

    if isinstance(raw, schemas.Farm):
        return strategy_inputs(raw, service.list_crops())
    warnings: list[str] = []
    demo = demo_econ()
    crops: dict[str, CropInfo] = {}

    def crop_info(crop_id: str) -> CropInfo:
        if crop_id not in crops:
            source = get_crop(crop_id) if get_crop else None
            if source is None:
                if crop_id not in DEMO_CROPS:
                    raise LookupError(f"нет культуры {crop_id}")
                crops[crop_id] = DEMO_CROPS[crop_id]
            else:
                crops[crop_id] = _crop_from_service(source, DEMO_CROPS.get(crop_id))
        return crops[crop_id]

    fields = []
    for f in _pick(raw, "fields", default=()):
        crop_id = str(_pick(f, "crop_id", "current_crop_id", "crop"))
        crop_info(crop_id)
        fields.append(
            FieldInfo(
                id=str(_pick(f, "id", "field_id")),
                name=str(_pick(f, "name", default=_pick(f, "id", "field_id"))),
                area_ha=float(_pick(f, "area_ha", "area")),
                crop_id=crop_id,
                raw=f,
            )
        )
    if not fields:
        raise LookupError("у хозяйства нет полей")
    for crop_id in DEMO_CROPS:  # кандидаты для перебора — весь справочник культур
        try:
            crop_info(crop_id)
        except Exception:  # noqa: BLE001
            crops.setdefault(crop_id, DEMO_CROPS[crop_id])

    def money(default: float, *names: str) -> float:
        value = _pick(raw, *names)
        if value is None:
            warnings.append(f"{names[0]}: нет в профиле хозяйства — взята демо-оценка")
            return default
        return float(value)

    herd = _pick(raw, "herd", default=None) or next(iter(_pick(raw, "herds", default=())), None)
    head = float(_pick(herd, "head_count", default=DEMO_HERD["head_count"])) if herd else 0.0
    dmi = float(_pick(herd, "dmi_kg_day", default=DEMO_HERD["dmi_kg_day"])) if herd else 0.0
    demand = herd_demand_dm_kg(head, dmi, DEMO_GRAZING)
    herd_scale = head / DEMO_HERD["head_count"]
    econ = FarmEcon(
        opening_cash_som=money(demo.opening_cash_som, "cash_som", "opening_cash_som", "cash"),
        reserve_som=money(demo.reserve_som, "family_reserve_som", "reserve_som"),
        family_by_month=_twelve(
            _pick(raw, "family_expense_by_month", "family_expense_month_som"),
            demo.family_by_month,
        ),
        debt_by_month=_twelve(_pick(raw, "debt_by_month"), demo.debt_by_month),
        milk_income_by_month=_twelve(
            _pick(raw, "milk_income_by_month"),
            tuple(v * herd_scale for v in demo.milk_income_by_month),
        ),
        herd_cost_by_month=_twelve(
            _pick(raw, "herd_cost_by_month"),
            tuple(v * herd_scale for v in demo.herd_cost_by_month),
        ),
        feed_demand_dm_kg=tuple(float(x) for x in demand),
        feed_opening_stock_dm_kg=float(
            _pick(raw, "feed_stock_dm_kg", default=float(demand[:5].sum()))
        ),
        feed_price_som_t=money(demo.feed_price_som_t, "feed_price_som_t"),
        feed_dm_share=demo.feed_dm_share,
        water_fee_som_m3=float(_pick(raw, "water_fee_som_m3", default=0.0)),
        payment_delay_days=float(_pick(raw, "payment_delay_days", default=demo.payment_delay_days)),
    )
    return FarmInputs(
        farm_id=farm_id,
        name=str(_pick(raw, "name", default=farm_id)),
        fields=tuple(fields),
        crops=crops,
        econ=econ,
        years=STUB_YEARS,
        status={"farm": "service", "water": "stub"},
        warnings=tuple(warnings),
    )


def _simulate_external(
    fn: Any, fld: FieldInfo, crop: CropInfo, scn: Scn, years: tuple[int, ...]
) -> FieldSims:
    """Вызов water.simulate_field по годам и приведение FieldSeason к массивам на 1 га."""
    n = len(years)
    mult = np.ones(n)
    gross = np.zeros((n, DECADES))
    deficit = np.zeros((n, DECADES))
    for i, year in enumerate(years):
        sowing = date(year, *crop.sowing_mmdd)
        season = fn(fld.raw or fld, crop.raw or crop, sowing, scn, year)
        mult[i] = float(_pick(season, "yield_multiplier", "yield_mult", "yield_factor"))
        for k, row in enumerate(_pick(season, "decades", "by_decade")):
            d = int(_pick(row, "decade", "decade_index", "index", default=k + 1)) - 1
            gross_mm = _pick(row, "gross_mm", "gross")
            if gross_mm is None:
                gross_mm = float(_pick(row, "gross_m3")) / (10.0 * fld.area_ha)
            deficit_mm = _pick(row, "deficit_mm", "deficit")
            if deficit_mm is None:
                deficit_mm = float(_pick(row, "deficit_m3")) / (10.0 * fld.area_ha)
            gross[i, d] = float(gross_mm)
            deficit[i, d] = float(deficit_mm)
    return FieldSims(mult, gross, deficit)


def load_inputs(farm_id: str) -> FarmInputs:
    """Хозяйство и вода от владельцев модулей; при любой их ошибке — демо-заглушка."""
    inputs: FarmInputs | None = None
    get_farm = _find(FARM_MODULES, "get_farm")
    if get_farm is not None:
        try:
            raw = get_farm(farm_id)
            if raw is not None:
                inputs = _farm_from_service(farm_id, raw, _find(FARM_MODULES, "get_crop"))
        except Exception as exc:  # noqa: BLE001
            if farm_id != "demo":
                from app.core.errors import ProblemError

                if isinstance(exc, ProblemError):
                    raise
                raise ProblemError(422, "Unprocessable Entity", str(exc)) from exc
            log.exception("farms.get_farm не подошёл — работаю на демо-хозяйстве")
            inputs = demo_inputs(farm_id, (f"farms.get_farm: {exc!r} — использовано демо",))
    if inputs is None:
        inputs = demo_inputs(farm_id)

    simulate = _find(WATER_MODULES, "simulate_field")
    history = _find(WATER_MODULES, "history_years")
    if simulate is not None and history is not None:
        try:
            years = tuple(int(y) for y in history())
            if years:
                candidate = replace(inputs, years=years, _water_fn=simulate)
                _simulate_external(  # пробный вызов: контракт действительно выполняется?
                    simulate, candidate.fields[0], candidate.crops[candidate.fields[0].crop_id],
                    Scn(), years[:1],
                )
                # вода посчитана сервисом М4–М6 на снимках NASA POWER — снимаем
                # предупреждение адаптера про демонстрационную модель воды
                warnings = tuple(w for w in inputs.warnings if not w.startswith("Вода и климат"))
                return replace(
                    candidate,
                    status={**inputs.status, "water": "service"},
                    warnings=(*warnings, "Вода и климат — NASA POWER (снимок), модель FAO-56"),
                )
        except Exception as exc:  # noqa: BLE001
            log.exception("water.simulate_field не подошёл — вода считается на заглушке")
            return replace(
                inputs,
                warnings=(*inputs.warnings, f"water.simulate_field: {exc!r} — вода на заглушке"),
            )
    return inputs
