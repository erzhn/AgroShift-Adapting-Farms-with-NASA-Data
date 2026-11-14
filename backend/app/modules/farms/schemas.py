"""Общие контракты для модулей воды, стратегий и канала (ТЗ 7.1–7.2).

DTO отделены от SQLAlchemy: их можно передавать в ядро после закрытия сессии.
Деньги — целые сомы, урожай — т/га, цена продукции — сом/т, геометрия — WGS84.
"""

from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field, model_validator
from pydantic import Field as Attr

from app.models.enums import (
    ClimateMode,
    Completeness,
    HerdPurpose,
    IrrigationMethod,
    MaturityClass,
    Rootstock,
    SourceType,
    Species,
)

Money = Annotated[int, Attr(strict=True, ge=0)]
Positive = Annotated[float, Attr(gt=0)]
NonNegative = Annotated[float, Attr(ge=0)]
Month = Annotated[int, Attr(strict=True, ge=1, le=12)]
Stage = Annotated[int, Attr(strict=True, ge=1, le=4)]
StageDays = Annotated[
    list[Annotated[int, Attr(strict=True, gt=0)]], Attr(min_length=4, max_length=4)
]


class Contract(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", allow_inf_nan=False)


class Source(Contract):
    source_type: SourceType
    confidence: float = Attr(ge=0, le=1)
    note: str = Attr(min_length=1)
    citation: str | None = None
    as_of: date | None = None


class Sourced(Contract):
    provenance: dict[str, Source] = Attr(default_factory=dict)


class Point(Contract):
    type: Literal["Point"] = "Point"
    coordinates: tuple[
        Annotated[float, Attr(ge=-180, le=180)], Annotated[float, Attr(ge=-90, le=90)]
    ]


class Polygon(Contract):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[
        list[tuple[Annotated[float, Attr(ge=-180, le=180)], Annotated[float, Attr(ge=-90, le=90)]]]
    ] = Attr(min_length=1)

    @model_validator(mode="after")
    def closed_rings(self) -> Self:
        for ring in self.coordinates:
            if len(ring) < 4 or ring[0] != ring[-1] or len(set(ring[:-1])) < 3:
                raise ValueError("Контур должен быть замкнут и иметь минимум три разные вершины")
        return self


class CostNorm(Sourced):
    id: UUID
    operation: str
    month: Month
    cost_som_ha: Money
    labour_h_ha: NonNegative
    equipment_type: str | None = None


class CropVariant(Sourced):
    id: UUID
    crop_id: UUID
    code: str
    maturity_class: MaturityClass
    stage_days_override: StageDays | None = None
    yield_potential_t_ha: Positive
    product: Literal["grain", "silage", "hay", "fruit"]
    costs: list[CostNorm] = Attr(default_factory=list)


class Price(Contract):
    id: UUID
    item_code: str
    region: str
    unit: Literal["t"] = "t"
    price_som: Money
    date: date
    source_type: SourceType
    confidence: float = Attr(ge=0, le=1)
    source_note: str


class Crop(Sourced):
    id: UUID
    code: str
    name_ky: str
    name_ru: str
    name_en: str
    family: str | None = None
    is_perennial: bool
    kc_ini: NonNegative
    kc_mid: NonNegative
    kc_end: NonNegative
    stage_days: StageDays
    height_m: Positive | None = None
    root_depth_m: Positive
    p_depletion: float = Attr(gt=0, lt=1)
    ky: NonNegative
    ky_stages: Annotated[list[NonNegative], Attr(min_length=4, max_length=4)] | None = None
    t_base: float
    t_min_kill: float | None = None
    gdd_required: Positive | None = None
    t_crit_heat: float | None = None
    k_heat: NonNegative | None = None
    water_critical_stages: list[Stage] | None = None
    variants: list[CropVariant] = Attr(default_factory=list)
    price: Price | None = None

    @computed_field
    @property
    def unknown_inputs(self) -> list[str]:
        unknown = []
        if self.price is None:
            unknown.append("price")
        if not self.variants:
            unknown.append("variants")
        unknown.extend(f"variants.{v.code}.costs" for v in self.variants if not v.costs)
        # Seasonal Ky must never silently substitute for four stage-specific Ky values.
        for name in ("ky_stages", "t_min_kill", "t_crit_heat", "k_heat"):
            if getattr(self, name) is None:
                unknown.append(name)
        return unknown

    @computed_field
    @property
    def completeness(self) -> Completeness:
        return Completeness.PARTIAL if self.unknown_inputs else Completeness.COMPLETE


class CropSeason(Sourced):
    id: UUID
    field_id: UUID
    crop_id: UUID
    crop_variant_id: UUID
    year: int = Attr(ge=1900, le=2200)
    is_main: bool = True
    sowing_date: date | None = None
    harvest_date: date | None = None
    planned_yield_t_ha: NonNegative | None = None
    actual_yield_t_ha: NonNegative | None = None

    @model_validator(mode="after")
    def ordered_dates(self) -> Self:
        if self.sowing_date and self.harvest_date and self.harvest_date < self.sowing_date:
            raise ValueError("Уборка не может предшествовать посеву")
        return self


class Field(Sourced):
    id: UUID
    farm_id: UUID
    name: str
    area_ha: Positive
    geometry: Polygon | None = None
    location: Point | None = None
    elevation_m: float | None = None
    slope_deg: Annotated[float, Attr(ge=0, le=90)] | None = None
    soil_type: str | None = None
    taw_mm_per_m: Positive | None = None
    irrigation_method: IrrigationMethod
    canal_id: UUID | None = None
    seasons: list[CropSeason] = Attr(default_factory=list)

    @model_validator(mode="after")
    def main_crop_per_year(self) -> Self:
        years = [s.year for s in self.seasons if s.is_main]
        if len(years) != len(set(years)):
            raise ValueError("На поле допустима одна основная культура в год")
        if any(s.field_id != self.id for s in self.seasons):
            raise ValueError("Сезон относится к другому полю")
        return self


class Orchard(Sourced):
    id: UUID
    farm_id: UUID
    field_id: UUID | None = None
    species: str
    variety: str | None = None
    planted_year: Annotated[int, Attr(ge=1800, le=2200)] | None = None
    density_trees_ha: Annotated[int, Attr(strict=True, gt=0)] | None = None
    rootstock: Rootstock | None = None
    yield_curve_id: str | None = None


class Herd(Sourced):
    id: UUID
    farm_id: UUID
    species: Species
    head_count: int = Attr(strict=True, ge=0)
    purpose: HerdPurpose
    feed_ration_id: str | None = None


class CashAccount(Sourced):
    id: UUID
    farm_id: UUID
    name: str
    balance_som: Annotated[int, Attr(strict=True)]
    as_of: date


class WaterRight(Contract):
    id: UUID
    farm_id: UUID
    canal_id: UUID
    season: int = Attr(ge=1900, le=2200)
    limit_m3: NonNegative | None = None
    # A seasonal right, NOT hours per irrigation turn.
    limit_hours: NonNegative | None = None
    flow_l_s: Positive | None = None
    turn_interval_days: Annotated[int, Attr(strict=True, gt=0)] | None = None
    turn_hours: Positive | None = None
    failure_months: list[Month] | None = None
    legal_basis: str | None = None
    source_type: SourceType
    confidence: float = Attr(ge=0, le=1)


class Farm(Sourced):
    id: UUID
    workspace_id: UUID
    name: str
    district: str | None = None
    village: str | None = None
    language: Literal["ky", "ru", "en"]
    family_reserve_som: Money | None = None
    labour_hours_month: Annotated[list[Money], Attr(min_length=12, max_length=12)] | None = None
    consent_agronomist: bool = False
    consent_canal_plan: bool = False
    consent_analytics: bool = False
    fields: list[Field] = Attr(default_factory=list)
    orchards: list[Orchard] = Attr(default_factory=list)
    herds: list[Herd] = Attr(default_factory=list)
    cash_accounts: list[CashAccount] = Attr(default_factory=list)
    water_rights: list[WaterRight] = Attr(default_factory=list)

    @model_validator(mode="after")
    def ownership(self) -> Self:
        for collection in (
            self.fields,
            self.orchards,
            self.herds,
            self.cash_accounts,
            self.water_rights,
        ):
            if any(item.farm_id != self.id for item in collection):
                raise ValueError("Объект относится к другому хозяйству")
        field_ids = {field.id for field in self.fields}
        if any(o.field_id and o.field_id not in field_ids for o in self.orchards):
            raise ValueError("Поле сада отсутствует в хозяйстве")
        return self

    @computed_field
    @property
    def area_ha(self) -> float:
        # Orchard is an asset on a field, never an additional area.
        return sum(field.area_ha for field in self.fields)

    @computed_field
    @property
    def cash_som(self) -> int | None:
        return sum(a.balance_som for a in self.cash_accounts) if self.cash_accounts else None

    @computed_field
    @property
    def unknown_inputs(self) -> list[str]:
        unknown = [
            name
            for name in ("family_reserve_som", "labour_hours_month")
            if getattr(self, name) is None
        ]
        if not self.cash_accounts:
            unknown.append("cash_accounts")
        if not self.water_rights:
            unknown.append("water_rights")
        for field in self.fields:
            for name in ("elevation_m", "soil_type", "taw_mm_per_m"):
                if getattr(field, name) is None:
                    unknown.append(f"fields.{field.id}.{name}")
        return unknown

    @computed_field
    @property
    def completeness(self) -> Completeness:
        return Completeness.PARTIAL if self.unknown_inputs else Completeness.COMPLETE


class ClimateParameters(Contract):
    year: Annotated[int, Attr(strict=True, ge=1900, le=2200)] | None = None
    percentile: Annotated[int, Attr(strict=True, ge=0, le=100)] | None = None


class Scenario(Sourced):
    id: UUID
    farm_id: UUID | None = None
    name: str
    preset_code: str | None = None
    water_supply_factor: float = Attr(default=1, ge=0.5, le=1.2)
    # None = whole season; [7, 8] = July–August only (FR-5.2).
    water_supply_months: Annotated[list[Month], Attr(min_length=1)] | None = None
    supply_shift_days: int = Attr(default=0, strict=True, ge=-30, le=30)
    temp_delta_c: float = Attr(default=0, ge=0, le=3)
    precip_factor: float = Attr(default=1, ge=0.5, le=1.3)
    price_factors: dict[str, Annotated[float, Attr(ge=0.5, le=1.5)]] = Attr(default_factory=dict)
    payment_delay_days: int = Attr(default=0, strict=True, ge=0, le=120)
    yield_factor: float = Attr(default=1, ge=0.7, le=1.3)
    climate_mode: ClimateMode
    climate_params: ClimateParameters

    @model_validator(mode="after")
    def climate_selection(self) -> Self:
        params = self.climate_params
        if self.climate_mode == ClimateMode.HISTORICAL_YEAR:
            if params.year is None or params.percentile is not None:
                raise ValueError("Исторический сценарий требует только год")
        elif self.climate_mode == ClimateMode.PERCENTILE:
            if params.percentile is None or params.year is not None:
                raise ValueError("Процентильный сценарий требует только процентиль")
        else:
            raise ValueError("CMIP6 не входит в контракт демо")
        if self.water_supply_months and len(set(self.water_supply_months)) != len(
            self.water_supply_months
        ):
            raise ValueError("Месяцы воздействия не должны повторяться")
        return self
