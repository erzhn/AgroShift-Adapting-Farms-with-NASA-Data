"""Validated API contracts for canal planning (FR-8.1 through FR-8.6)."""

from __future__ import annotations

import math
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ProposalResponse, SourceType

DecadeValues = Annotated[list[float], Field(min_length=36, max_length=36)]


class GeoJSONMultiLineString(BaseModel):
    type: Literal["MultiLineString"]
    coordinates: list[list[list[float]]]

    @field_validator("coordinates")
    @classmethod
    def validate_lines(cls, lines: list[list[list[float]]]) -> list[list[list[float]]]:
        if not lines:
            raise ValueError("at least one canal line is required")
        for line in lines:
            if len(line) < 2:
                raise ValueError("each canal line needs at least two points")
            _validate_coordinates([point for point in line])
        return lines


class GeoJSONMultiPolygon(BaseModel):
    type: Literal["MultiPolygon"]
    coordinates: list[list[list[list[float]]]]

    @field_validator("coordinates")
    @classmethod
    def validate_polygons(
        cls, polygons: list[list[list[list[float]]]]
    ) -> list[list[list[list[float]]]]:
        if not polygons:
            raise ValueError("at least one catchment polygon is required")
        for polygon in polygons:
            if not polygon:
                raise ValueError("each polygon needs an outer ring")
            for ring in polygon:
                if len(ring) < 4 or ring[0][:2] != ring[-1][:2]:
                    raise ValueError("polygon rings must have at least four points and be closed")
                _validate_coordinates(ring)
        return polygons


def _validate_coordinates(points: list[list[float]]) -> None:
    for point in points:
        if len(point) < 2 or not all(math.isfinite(value) for value in point):
            raise ValueError("coordinates must contain finite longitude and latitude")
        lon, lat = point[:2]
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise ValueError("coordinates must use WGS84 longitude/latitude ranges")


class CanalCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    avp_name: Annotated[str | None, Field(max_length=200)] = None
    geometry: GeoJSONMultiLineString
    snow_catchment_geometry: GeoJSONMultiPolygon
    conveyance_efficiency: Annotated[float, Field(ge=0.35, le=0.70)] = 0.5


class CanalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    avp_name: str | None
    conveyance_efficiency: float
    invite_code: str | None
    geometry: GeoJSONMultiLineString | None = None
    snow_catchment_geometry: GeoJSONMultiPolygon | None = None


class SupplyPoint(BaseModel):
    decade: Annotated[int, Field(ge=1, le=36)]
    volume_m3: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    source_type: SourceType = SourceType.USER_ESTIMATE
    reliability: Annotated[float, Field(ge=0, le=1)] = 0.8


class SupplyScheduleInput(BaseModel):
    season: Annotated[int, Field(ge=2000, le=2200)]
    decades: Annotated[list[SupplyPoint], Field(min_length=1, max_length=36)]

    @model_validator(mode="after")
    def unique_decades(self) -> SupplyScheduleInput:
        decades = [point.decade for point in self.decades]
        if len(decades) != len(set(decades)):
            raise ValueError("each decade may be provided only once")
        return self


class SupplyRead(BaseModel):
    decade: int
    volume_m3: float
    source_type: SourceType
    reliability: float


class CanalFarmMapItem(BaseModel):
    farm_id: UUID
    farm_name: str
    field_id: UUID
    field_name: str
    area_ha: float
    location: dict | None
    geometry: dict | None
    crop_code: str | None
    crop_name: str | None
    sowing_date: date | None


class ShiftSimulation(BaseModel):
    shift_days: Literal[-20, -10, 10, 20]
    demand_m3_by_decade: DecadeValues
    crop_demand_m3_by_decade: Annotated[dict[str, DecadeValues], Field(min_length=1)]
    income_loss_som: Annotated[float, Field(ge=0, allow_inf_nan=False)]

    @field_validator("demand_m3_by_decade")
    @classmethod
    def finite_non_negative_demand(cls, values: list[float]) -> list[float]:
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("demand values must be finite and non-negative")
        return values

    @model_validator(mode="after")
    def crop_series_match_total(self) -> ShiftSimulation:
        _validate_crop_totals(self.demand_m3_by_decade, self.crop_demand_m3_by_decade)
        return self


class FarmDemandSimulation(BaseModel):
    """Output of simulate_field plus the farm/strategy module's income estimate."""

    farm_id: UUID
    sowing_date: date
    demand_m3_by_decade: DecadeValues
    crop_demand_m3_by_decade: Annotated[dict[str, DecadeValues], Field(min_length=1)]
    expected_income_som: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    income_loss_per_m3: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    shift_options: Annotated[list[ShiftSimulation], Field(max_length=4)] = Field(
        default_factory=list
    )

    @field_validator("demand_m3_by_decade")
    @classmethod
    def finite_non_negative_demand(cls, values: list[float]) -> list[float]:
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("demand values must be finite and non-negative")
        return values

    @model_validator(mode="after")
    def unique_shifts(self) -> FarmDemandSimulation:
        shifts = [option.shift_days for option in self.shift_options]
        if len(shifts) != len(set(shifts)):
            raise ValueError("each sowing-date alternative may be provided only once")
        _validate_crop_totals(self.demand_m3_by_decade, self.crop_demand_m3_by_decade)
        return self


def _validate_crop_totals(total: list[float], crops: dict[str, list[float]]) -> None:
    if any(not code.strip() for code in crops):
        raise ValueError("crop codes must not be empty")
    if any(
        not math.isfinite(value) or value < 0
        for series in crops.values()
        for value in series
    ):
        raise ValueError("crop demand values must be finite and non-negative")
    if any(
        abs(sum(series[index] for series in crops.values()) - total[index]) > 0.01
        for index in range(36)
    ):
        raise ValueError("crop demand series must sum to the farm's total demand per decade")


class CoordinatePlanInput(BaseModel):
    season: Annotated[int, Field(ge=2000, le=2200)]
    # Normally generated by the canal service from persisted farm data and
    # water.service.simulate_field. Optional explicit values remain useful for
    # deterministic API-level tests and internal callers.
    simulations: Annotated[list[FarmDemandSimulation], Field(min_length=1)] | None = None
    water_model_version: Annotated[str | None, Field(min_length=1, max_length=32)] = None
    snapshot_ids: Annotated[list[str], Field(max_length=16)] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_farms(self) -> CoordinatePlanInput:
        ids = [simulation.farm_id for simulation in self.simulations or []]
        if len(ids) != len(set(ids)):
            raise ValueError("each farm may appear only once")
        return self


class ProposalResponseInput(BaseModel):
    response: ProposalResponse
    counter_note: Annotated[str | None, Field(max_length=2000)] = None

    @model_validator(mode="after")
    def counter_requires_note(self) -> ProposalResponseInput:
        if self.response == ProposalResponse.PENDING:
            raise ValueError("response must be agree, reject, or counter")
        if self.response == ProposalResponse.COUNTER and not (self.counter_note or "").strip():
            raise ValueError("counter_note is required for a counter proposal")
        return self


class ProposalRead(BaseModel):
    id: UUID
    farm_id: UUID
    change: dict
    water_delta_m3: float
    response: ProposalResponse


class CanalPlanRead(BaseModel):
    id: UUID
    canal_id: UUID
    season: int
    status: str
    summary: dict
    proposals: list[ProposalRead]
