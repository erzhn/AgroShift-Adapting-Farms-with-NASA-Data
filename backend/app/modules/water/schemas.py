"""Схемы модуля «Вода и климат».

FieldSeason — внутренний контракт для модулей стратегий и канала (результат
water.service.simulate_field). Добавлять поля можно; переименовывать и удалять —
только с согласия тех, кто их использует.

Единицы: вода — мм и м³ (1 мм на 1 га = 10 м³), даты — ISO, декады — индекс 1..36.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

StageName = Literal["ini", "dev", "mid", "late"]
DecadeStatus = Literal["ok", "deficit_lt20", "deficit_ge20"]
SourceTypeName = Literal["measured", "satellite", "model", "reference", "user_estimate",
                         "unknown"]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Percentiles(Frozen):
    p10: float
    p50: float
    p90: float


class InputValue(Frozen):
    """Вход расчёта со статусом (раздел 3.5: измеренное отделено от предположенного)."""

    value: float | str | None
    unit: str | None = None
    source_type: SourceTypeName
    range: tuple[float, float] | None = None   # справочный диапазон для Монте-Карло (М10)


class DecadeWater(Frozen):
    """Вода поля за одну декаду сезона (выход М5)."""

    decade: int = Field(ge=1, le=36, description="индекс декады 1..36")
    start: date
    end: date
    days: int
    stage: StageName
    et0_mm: float
    etc_mm: float = Field(description="потребность культуры ETc")
    eta_mm: float = Field(description="фактическая эвапотранспирация ETa")
    precip_mm: float
    eff_precip_mm: float = Field(description="эффективные осадки = Σ(P − RO − DP от дождя)")
    runoff_mm: float
    deep_percolation_mm: float
    irrigation_net_mm: float = Field(description="полив, дошедший до корней")
    need_net_mm: float = Field(description="потребность в поливе нетто = ETc − эфф. осадки")
    need_gross_m3: float = Field(description="потребность брутто на водовыпуске хозяйства")
    gross_mm: float = Field(description="то же слоем на 1 га: need_gross_m3 / (10 · A)")
    need_head_m3: float = Field(description="то же на голове канала (÷ η_conv)")
    received_m3: float = Field(description="получено по очереди на водовыпуске хозяйства")
    used_m3: float = Field(description="из полученного принято полем (почва не берёт "
                                       "больше, чем нужно до полной влагоёмкости)")
    deficit_mm: float = Field(description="дефицит нетто = потребность − полученное × η")
    deficit_m3: float = Field(description="дефицит брутто на водовыпуске")
    deficit_pct: float = Field(description="дефицит, % от потребности")
    stress_pct: float = Field(description="недобор воды культурой = (1 − ETa/ETc)·100")
    ks_avg: float = Field(description="средний коэффициент водного стресса")
    dr_end_mm: float = Field(description="истощение корневой зоны на конец декады")
    raw_mm: float
    taw_mm: float
    turns_planned: int
    turns_failed: int
    hot_days: int = Field(description="дней с Tmax > 35 °C")
    status: DecadeStatus = Field(
        description="для обводки поля (FR-2.1). Красное/жёлтое — когда культура уже "
                    "недобрала воду, либо подано меньше потребности и легкодоступный "
                    "запас почвы исчерпан (D_r > RAW)")


class StageYield(Frozen):
    """Потеря урожая от дефицита по стадиям — «в какую фазу вода важнее всего» (FR-3.3)."""

    stage: StageName
    days: int
    etc_mm: float
    eta_mm: float
    ratio: float = Field(description="ETa / ETc")
    ky: float
    factor: float = Field(description="множитель урожая стадии")


class Alert(Frozen):
    """Тревожный маркер для шкалы (FR-2.5)."""

    type: Literal["water_deficit", "frost_in_bloom", "heat_in_flowering", "resow_risk"]
    decade: int | None = None
    days: int | None = None
    value: float | None = None


class DailySeries(Frozen):
    """Суточные ряды для графика истощения почвы (FR-3.2)."""

    dates: list[date]
    et0: list[float]
    etc: list[float]
    eta: list[float]
    precip: list[float]
    irrigation: list[float]
    dr: list[float]
    raw: list[float]
    taw: list[float]
    ks: list[float]


class SeasonTotals(Frozen):
    et0_mm: float
    etc_mm: float
    eta_mm: float
    precip_mm: float
    eff_precip_mm: float
    irrigation_net_mm: float
    need_net_mm: float
    need_gross_m3: float
    need_head_m3: float
    received_m3: float
    used_m3: float
    deficit_m3: float
    deficit_pct: float


class FieldSeason(Frozen):
    """Сезон одного поля в погоде одного исторического года."""

    field_id: str
    crop_code: str
    year: int = Field(description="исторический год погоды NASA")
    sowing_date: date
    harvest_date: date
    season_days: int
    stage_days: tuple[int, int, int, int]
    area_ha: float
    decades: list[DecadeWater]
    stages: list[StageYield]
    totals: SeasonTotals
    worst_decade: int | None = Field(description="декада с наибольшим дефицитом, м³")

    yield_multiplier: float = Field(description="Ya/Ym = F_water · F_heat · F_frost, 0..1. "
                                                "Сценарный yield_factor сюда НЕ входит")
    f_water: float
    f_heat: float
    f_frost: float
    yield_potential_t_ha: float | None
    yield_t_ha: float | None = Field(description="модельная оценка, не точнее 0,1 т/га")
    yield_status: Literal["model_estimate"] = "model_estimate"

    alerts: list[Alert]
    balance_error_mm: float = Field(description="невязка водного баланса за сезон")

    # прослеживаемость (раздел 3.5, FR-11.1)
    completeness: Literal["complete", "partial"]
    unknown_inputs: list[str]
    inputs: dict[str, InputValue]
    snapshots: list[str]
    model_version: str
    et0_method: Literal["penman_monteith", "mixed", "hargreaves"]
    kc_used: tuple[float, float, float] = Field(description="Kc ini/mid/end после коррекции")

    daily: DailySeries | None = None


# ---------- GET /fields/{id}/water-balance ----------

class EnsembleDecade(Frozen):
    decade: int
    need_gross_m3: Percentiles
    received_m3: Percentiles
    deficit_pct: Percentiles
    years_deficit_ge20: int = Field(description="в скольких годах дефицит ≥ 20 %")


class YearSummary(Frozen):
    year: int
    yield_multiplier: float
    deficit_m3: float
    worst_decade: int | None


class Ensemble(Frozen):
    """Те же расчёты на всех исторических годах NASA — диапазон вместо точки."""

    years: list[int]
    yield_multiplier: Percentiles
    yield_t_ha: Percentiles | None
    need_gross_m3: Percentiles
    deficit_m3: Percentiles
    decades: list[EnsembleDecade]
    per_year: list[YearSummary]


class ClimateCell(Frozen):
    """Ячейка сетки NASA POWER — «климат района», не «данные вашего поля» (6.3)."""

    snapshot: str
    point_name: str | None
    center: tuple[float, float] = Field(description="[lon, lat]")
    bbox: tuple[float, float, float, float] = Field(description="[minlon, minlat, maxlon, maxlat]")
    cell_elevation_m: float
    resolution_note_key: str = "climate.resolution_note"


class FieldInfo(Frozen):
    """Паспорт поля в части воды (FR-3.1)."""

    id: str
    name: str
    farm_id: str | None = None
    farm_name: str | None = None
    area_ha: float
    lat: float | None
    lon: float | None
    elevation_m: float | None
    soil_type: str | None
    irrigation_method: str
    crop_code: str
    crop_name: str
    sowing_date: date
    source: Literal["farms", "demo"] = Field(description="откуда взят профиль поля")


class WaterBalanceResponse(Frozen):
    field: FieldInfo
    cell: ClimateCell
    strategy: str | None
    scenario: str | None
    year: int
    year_mode: Literal["requested", "scenario", "median"]
    season: FieldSeason
    ensemble: Ensemble


# ---------- GET /fields/{id}/climate ----------

class ClimateDay(Frozen):
    date: date
    tmax: float
    tmin: float
    tmean: float
    precip: float
    rs: float
    ws2m: float
    rh_min: float
    et0: float
    et0_method: Literal["pm", "hs"]


class ClimateDecadeNorm(Frozen):
    decade: int
    et0_mm: Percentiles
    precip_mm: Percentiles
    tmean_c: Percentiles
    hot_days_mean: float


class FrostDates(Frozen):
    year: int
    last_spring_frost: date | None
    first_autumn_frost: date | None


class QCInfo(Frozen):
    days: int
    missing: int
    out_of_range: int
    interpolated: int
    filled_with_norm: int


class ClimateResponse(Frozen):
    field_id: str
    cell: ClimateCell
    date_from: date
    date_to: date
    field_elevation_m: float | None
    temperature_shift_c: float = Field(description="поправка температуры на высоту поля")
    et0_method: str
    days: list[ClimateDay]
    decade_norms: list[ClimateDecadeNorm]
    frost: list[FrostDates]
    history_years: list[int]
    qc: QCInfo
    model_version: str
    attribution: str


# ---------- GET /data-sources ----------

class SnapshotInfo(Frozen):
    code: str
    point_name: str | None
    lat: float
    lon: float
    cell: ClimateCell
    period_start: date
    period_end: date
    fetched_at: datetime
    rows: int
    sha256: str
    product_version: str | None
    missing_values: int


class Dataset(Frozen):
    id: str
    name: str
    provider: str
    parameters: str
    resolution: str
    frequency: str
    used_for: str
    limitations: str
    priority: str
    status: Literal["active", "planned"]
    url: str
    snapshots: list[SnapshotInfo] = []


class DataSourcesResponse(Frozen):
    attribution: str
    model_version: str
    offline_ready: bool = Field(description="расчёты идут по локальным снимкам, без сети")
    datasets: list[Dataset]
