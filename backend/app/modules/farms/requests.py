"""Write contracts: omitted PATCH fields are preserved; explicit null clears optional data."""

from datetime import date
from typing import Annotated, ClassVar, Literal, Self
from uuid import UUID

from pydantic import Field as Attr
from pydantic import StringConstraints, model_validator

from app.models.enums import IrrigationMethod
from app.modules.farms.schemas import Contract, Money, NonNegative, Point, Polygon, Positive

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Balance = Annotated[int, Attr(strict=True, ge=-9007199254740991, le=9007199254740991)]
Count = Annotated[int, Attr(strict=True, ge=0, le=1000000)]


class FarmCreate(Contract):
    name: Name
    district: ShortText | None = None
    village: ShortText | None = None
    language: Literal["ru", "ky", "en"] = "ru"
    family_reserve_som: Money | None = None
    cash_som: Balance | None = None
    cow_count: Count | None = None
    labour_hours_month: Annotated[list[Money], Attr(min_length=12, max_length=12)] | None = None
    consent_agronomist: bool = False
    consent_canal_plan: bool = False
    consent_analytics: bool = False


class Patch(Contract):
    non_nullable: ClassVar[set[str]] = set()

    @model_validator(mode="after")
    def explicit_values(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Передайте хотя бы одно изменённое поле")
        if any(getattr(self, key) is None for key in self.model_fields_set & self.non_nullable):
            raise ValueError("Обязательные поля нельзя очистить")
        return self


class FarmPatch(Patch):
    non_nullable = {
        "name",
        "language",
        "consent_agronomist",
        "consent_canal_plan",
        "consent_analytics",
    }
    name: Name | None = None
    district: ShortText | None = None
    village: ShortText | None = None
    language: Literal["ru", "ky", "en"] | None = None
    family_reserve_som: Money | None = None
    cash_som: Balance | None = None
    cow_count: Count | None = None
    labour_hours_month: Annotated[list[Money], Attr(min_length=12, max_length=12)] | None = None
    consent_agronomist: bool | None = None
    consent_canal_plan: bool | None = None
    consent_analytics: bool | None = None


class SeasonWrite(Contract):
    crop_variant_id: UUID
    year: int = Attr(strict=True, ge=1900, le=2200)
    sowing_date: date | None = None
    harvest_date: date | None = None
    planned_yield_t_ha: NonNegative | None = None

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.sowing_date and self.harvest_date and self.harvest_date < self.sowing_date:
            raise ValueError("Уборка не может предшествовать посеву")
        if self.harvest_date and self.harvest_date.year != self.year:
            raise ValueError("Год сезона должен совпадать с годом уборки")
        return self


class FieldCreate(Contract):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    area_ha: Annotated[float, Attr(gt=0, le=1000000)] | None = None
    geometry: Polygon | None = None
    location: Point | None = None
    elevation_m: Annotated[float, Attr(ge=-500, le=9000)] | None = None
    slope_deg: Annotated[float, Attr(ge=0, le=90)] | None = None
    soil_type: Annotated[str, StringConstraints(max_length=32)] | None = None
    taw_mm_per_m: Positive | None = None
    irrigation_method: IrrigationMethod = IrrigationMethod.FURROW
    canal_id: UUID | None = None
    season: SeasonWrite | None = None

    @model_validator(mode="after")
    def located(self) -> Self:
        if self.geometry is None and (self.location is None or self.area_ha is None):
            raise ValueError("Нужен контур или точка с площадью")
        return self


class FieldPatch(Patch):
    non_nullable = {"name", "area_ha", "irrigation_method", "season"}
    name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
        | None
    ) = None
    area_ha: Annotated[float, Attr(gt=0, le=1000000)] | None = None
    geometry: Polygon | None = None
    location: Point | None = None
    elevation_m: Annotated[float, Attr(ge=-500, le=9000)] | None = None
    slope_deg: Annotated[float, Attr(ge=0, le=90)] | None = None
    soil_type: Annotated[str, StringConstraints(max_length=32)] | None = None
    taw_mm_per_m: Positive | None = None
    irrigation_method: IrrigationMethod | None = None
    canal_id: UUID | None = None
    season: SeasonWrite | None = None
