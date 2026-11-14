"""Database operations for canal setup, supply schedules, and plan snapshots."""

from __future__ import annotations

import json
import secrets
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from geoalchemy2.elements import WKTElement
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from agroshift_core.canal import CanalInputError, FarmDemand, ShiftOption, coordinate_canal
from app.core.errors import NotFoundError, ProblemError
from app.modules.water import service as water_service
from app.modules.water.inputs import CropInput
from app.models.catalog import CostNorm, Crop, CropVariant, PriceItem
from app.models.enums import CanalPlanStatus, ProposalResponse
from app.models.farm import CropSeason, Farm, Field
from app.models.water import Canal, CanalPlan, CanalProposal, SupplySchedule, WaterRight
from app.schemas.canal import (
    CanalCreate,
    CanalFarmMapItem,
    CanalPlanRead,
    CanalRead,
    CoordinatePlanInput,
    FarmDemandSimulation,
    ProposalRead,
    ShiftSimulation,
    SupplyRead,
    SupplyScheduleInput,
)


def _line_wkt(geometry: dict) -> str:
    lines = geometry["coordinates"]
    line_text = []
    for line in lines:
        line_text.append("(" + ", ".join(" ".join(map(str, point[:2])) for point in line) + ")")
    return "MULTILINESTRING (" + ", ".join(line_text) + ")"


def _polygon_wkt(geometry: dict) -> str:
    polygons = geometry["coordinates"]
    polygon_text = []
    for polygon in polygons:
        rings = []
        for ring in polygon:
            rings.append("(" + ", ".join(" ".join(map(str, point[:2])) for point in ring) + ")")
        polygon_text.append("(" + ", ".join(rings) + ")")
    return "MULTIPOLYGON (" + ", ".join(polygon_text) + ")"


def _canal_read(db: Session, canal: Canal) -> CanalRead:
    geometry, catchment = db.execute(
        select(func.ST_AsGeoJSON(Canal.geometry), func.ST_AsGeoJSON(Canal.snow_catchment_geometry))
        .where(Canal.id == canal.id)
    ).one()
    return CanalRead(
        id=canal.id,
        name=canal.name,
        avp_name=canal.avp_name,
        conveyance_efficiency=canal.conveyance_efficiency,
        invite_code=canal.invite_code,
        geometry=json.loads(geometry) if geometry else None,
        snow_catchment_geometry=json.loads(catchment) if catchment else None,
    )


def list_canals(db: Session) -> list[CanalRead]:
    return [_canal_read(db, canal) for canal in db.scalars(select(Canal).order_by(Canal.name))]


def get_canal(db: Session, canal_id: UUID) -> Canal:
    canal = db.get(Canal, canal_id)
    if canal is None:
        raise NotFoundError("Canal", canal_id)
    return canal


def create_canal(db: Session, data: CanalCreate) -> CanalRead:
    canal = Canal(
        name=data.name.strip(),
        avp_name=data.avp_name.strip() if data.avp_name else None,
        geometry=WKTElement(_line_wkt(data.geometry.model_dump()), srid=4326),
        snow_catchment_geometry=WKTElement(
            _polygon_wkt(data.snow_catchment_geometry.model_dump()), srid=4326
        ),
        conveyance_efficiency=data.conveyance_efficiency,
        invite_code=secrets.token_urlsafe(9)[:16],
    )
    db.add(canal)
    db.commit()
    db.refresh(canal)
    return _canal_read(db, canal)


def list_supply(db: Session, canal_id: UUID, season: int) -> list[SupplyRead]:
    get_canal(db, canal_id)
    rows = db.scalars(
        select(SupplySchedule)
        .where(SupplySchedule.canal_id == canal_id, SupplySchedule.season == season)
        .order_by(SupplySchedule.decade_index)
    )
    return [
        SupplyRead(
            decade=row.decade_index + 1,
            volume_m3=row.volume_m3,
            source_type=row.source_type,
            reliability=row.reliability,
        )
        for row in rows
    ]


def save_supply(db: Session, canal_id: UUID, data: SupplyScheduleInput) -> list[SupplyRead]:
    get_canal(db, canal_id)
    existing = {
        row.decade_index: row
        for row in db.scalars(
            select(SupplySchedule).where(
                SupplySchedule.canal_id == canal_id,
                SupplySchedule.season == data.season,
            )
        )
    }
    for point in data.decades:
        index = point.decade - 1
        row = existing.get(index)
        if row is None:
            row = SupplySchedule(canal_id=canal_id, season=data.season, decade_index=index)
            db.add(row)
        row.volume_m3 = point.volume_m3
        row.source_type = point.source_type
        row.reliability = point.reliability
    db.commit()
    return list_supply(db, canal_id, data.season)


def list_canal_farms(db: Session, canal_id: UUID, season: int) -> list[CanalFarmMapItem]:
    get_canal(db, canal_id)
    rows = db.execute(
        select(
            Farm.id,
            Farm.name,
            Field.id,
            Field.name,
            Field.area_ha,
            func.ST_AsGeoJSON(Field.location),
            func.ST_AsGeoJSON(Field.geometry),
            Crop.code,
            Crop.name_ru,
            CropSeason.sowing_date,
        )
        .join(Field, Field.farm_id == Farm.id)
        .outerjoin(
            CropSeason,
            and_(CropSeason.field_id == Field.id,
                 CropSeason.year == season,
                 CropSeason.is_main.is_(True)),
        )
        .outerjoin(CropVariant, CropVariant.id == CropSeason.crop_variant_id)
        .outerjoin(Crop, Crop.id == CropVariant.crop_id)
        .where(Field.canal_id == canal_id, Farm.consent_canal_plan.is_(True))
        .order_by(Farm.name, Field.name)
    )
    return [
        CanalFarmMapItem(
            farm_id=row[0],
            farm_name=row[1],
            field_id=row[2],
            field_name=row[3],
            area_ha=row[4],
            location=json.loads(row[5]) if row[5] else None,
            geometry=json.loads(row[6]) if row[6] else None,
            crop_code=row[7],
            crop_name=row[8],
            sowing_date=row[9],
        )
        for row in rows
    ]


def _water_right_m3(right: WaterRight) -> float:
    if right.limit_m3 is not None:
        return right.limit_m3
    if right.limit_hours is not None and right.flow_l_s is not None:
        return right.limit_hours * 3600 * right.flow_l_s / 1000
    raise ProblemError(
        422,
        "Missing water right",
        f"Farm {right.farm_id} has no volume or flow-based water right for this season",
    )


def _series_by_decade(field_season) -> list[float]:
    """Return gross demand at each farm intake, indexed by calendar decade (1..36)."""
    values = [0.0] * 36
    for decade in field_season.decades:
        values[decade.decade - 1] += float(decade.need_gross_m3)
    return values


def _sum_crop_series(series: dict[str, list[float]]) -> list[float]:
    return [sum(values[index] for values in series.values()) for index in range(36)]


def _simulate_canal_farms(
    db: Session, canal: Canal, season: int, *, include_shifts: bool
) -> tuple[list[FarmDemandSimulation], str, list[str]]:
    """Build farm-level NASA water simulations from the persisted canal roster."""
    rows = db.execute(
        select(Field, Farm, CropSeason, Crop, CropVariant)
        .join(Farm, Farm.id == Field.farm_id)
        .join(CropSeason, CropSeason.field_id == Field.id)
        .join(CropVariant, CropVariant.id == CropSeason.crop_variant_id)
        .join(Crop, Crop.id == CropVariant.crop_id)
        .where(
            Field.canal_id == canal.id,
            CropSeason.year == season,
            CropSeason.is_main.is_(True),
            Farm.consent_canal_plan.is_(True),
        )
        .order_by(Farm.id, Field.id)
    ).all()
    if not rows:
        raise ProblemError(
            422,
            "No consenting farms",
            "No farms with a main crop and consent to canal planning are available",
        )

    weather_years = water_service.history_years()
    if not weather_years:
        raise ProblemError(503, "No climate snapshots", "NASA POWER history is unavailable")
    weather_year = max(weather_years)

    farm_ids = {farm.id for _, farm, *_ in rows}
    rights = {
        right.farm_id: right
        for right in db.scalars(
            select(WaterRight).where(
                WaterRight.canal_id == canal.id,
                WaterRight.season == season,
                WaterRight.farm_id.in_(farm_ids),
            )
        )
    }
    if set(rights) != farm_ids:
        missing = sorted(str(item) for item in farm_ids - set(rights))
        raise ProblemError(422, "Missing water rights", "No seasonal water right for: " + ", ".join(missing))

    irrigated_area: dict[UUID, float] = {}
    for field, farm, *_ in rows:
        if getattr(field.irrigation_method, "value", field.irrigation_method) != "none":
            irrigated_area[farm.id] = irrigated_area.get(farm.id, 0.0) + field.area_ha

    crop_ids = {crop.id for _, _, _, crop, _ in rows}
    variants = {variant.id: variant for _, _, _, _, variant in rows}
    prices = db.scalars(
        select(PriceItem)
        .where(
            PriceItem.item_kind == "crop",
            PriceItem.region == "chuy",
            PriceItem.unit == "t",
            PriceItem.farm_id.is_(None),
            PriceItem.item_code.in_({crop.code for _, _, _, crop, _ in rows}),
        )
        .order_by(PriceItem.date.desc())
    ).all()
    price_by_code = {}
    for price in prices:
        price_by_code.setdefault(price.item_code, price)
    costs_by_variant = {
        variant_id: float(total or 0.0)
        for variant_id, total in db.execute(
            select(CostNorm.crop_variant_id, func.sum(CostNorm.cost_som_ha))
            .where(CostNorm.crop_variant_id.in_({variant.id for variant in variants.values()}))
            .group_by(CostNorm.crop_variant_id)
        )
    }

    grouped: dict[UUID, list[tuple[Field, Farm, CropSeason, Crop, CropVariant]]] = {}
    for row in rows:
        grouped.setdefault(row[1].id, []).append(row)

    def simulate_group(field_rows, shift_days: int, *, need_prices: bool):
        crop_series: dict[str, list[float]] = {}
        income = 0.0
        representative_sowing = None
        snapshots: set[str] = set()
        model_version = None
        for field, farm, crop_season, crop, variant in field_rows:
            right = rights[farm.id]
            base_date = crop_season.sowing_date or date(
                season, 4 if crop.is_perennial else 5, 1
            )
            sowing = base_date + timedelta(days=shift_days)
            if sowing.year != season:
                raise ProblemError(422, "Invalid sowing shift", "Shift moves sowing outside the crop season")
            representative_sowing = representative_sowing or base_date
            water = {
                "turn_interval_days": right.turn_interval_days,
                "turn_hours": right.turn_hours,
                "flow_l_s": right.flow_l_s,
                "limit_m3": right.limit_m3,
                "limit_hours": right.limit_hours,
                "failure_months": right.failure_months or (),
                "share": field.area_ha / irrigated_area.get(farm.id, field.area_ha),
                "season_start": (4, 1),
                "season_end": (9, 30),
                "conveyance_efficiency": canal.conveyance_efficiency,
                "source_type": right.source_type,
            }
            crop_input = replace(
                CropInput.from_any(crop),
                yield_potential_t_ha=variant.yield_potential_t_ha,
                stage_days=tuple(variant.stage_days_override or crop.stage_days),
            )
            result = water_service.simulate_field(
                field,
                crop_input,
                sowing,
                year=weather_year,
                water=water,
            )
            snapshots.update(result.snapshots)
            model_version = result.model_version
            target = crop_series.setdefault(crop.code, [0.0] * 36)
            for index, value in enumerate(_series_by_decade(result)):
                target[index] += value

            price = price_by_code.get(crop.code)
            if price is None:
                if need_prices:
                    raise ProblemError(
                        422,
                        "Missing crop price",
                        f"No Chuy price (som/t) is recorded for crop {crop.code}",
                    )
                continue
            yield_t_ha = result.yield_t_ha
            if yield_t_ha is None:
                continue
            revenue = float(yield_t_ha) * field.area_ha * float(price.price_som)
            costs = costs_by_variant.get(variant.id, 0.0) * field.area_ha
            income += max(0.0, revenue - costs)
        total_series = _sum_crop_series(crop_series)
        return total_series, crop_series, income, representative_sowing, model_version, snapshots

    simulations = []
    all_snapshots: set[str] = set()
    model_version = None
    for farm_id, farm_rows in grouped.items():
        baseline = simulate_group(farm_rows, 0, need_prices=include_shifts)
        demand, crop_demand, baseline_income, sowing, farm_model, snapshots = baseline
        model_version = model_version or farm_model
        all_snapshots.update(snapshots)
        options = []
        if include_shifts:
            shifted_results = {}
            for shift_days in (-20, -10, 10, 20):
                try:
                    shifted = simulate_group(farm_rows, shift_days, need_prices=True)
                except ProblemError:
                    continue
                shifted_demand, shifted_crops, shifted_income, *_ = shifted
                shifted_results[shift_days] = (
                    shifted_demand,
                    shifted_crops,
                    max(0.0, baseline_income - shifted_income),
                )
            for shift_days in (-20, -10, 10, 20):
                if shift_days not in shifted_results:
                    continue
                shifted_demand, shifted_crops, income_loss = shifted_results[shift_days]
                nearer_shift = shift_days // 2
                if abs(shift_days) == 20 and nearer_shift in shifted_results:
                    income_loss = max(income_loss, shifted_results[nearer_shift][2])
                options.append(
                    ShiftSimulation(
                        shift_days=shift_days,
                        demand_m3_by_decade=shifted_demand,
                        crop_demand_m3_by_decade=shifted_crops,
                        income_loss_som=income_loss,
                    )
                )
        total_demand = sum(demand)
        simulations.append(
            FarmDemandSimulation(
                farm_id=farm_id,
                sowing_date=sowing or date(season, 5, 1),
                demand_m3_by_decade=demand,
                crop_demand_m3_by_decade=crop_demand,
                expected_income_som=baseline_income,
                income_loss_per_m3=baseline_income / total_demand if total_demand else 0.0,
                shift_options=options,
            )
        )
    if not simulations:
        raise ProblemError(422, "No farm simulations", "No eligible fields could be simulated")
    return simulations, model_version or "unknown", sorted(all_snapshots)


def _coordinate_input(db: Session, canal: Canal, data: CoordinatePlanInput):
    if data.simulations is None:
        raise ProblemError(422, "Missing simulations", "Canal simulations were not generated")
    supply_rows = list(
        db.scalars(
            select(SupplySchedule)
            .where(SupplySchedule.canal_id == canal.id, SupplySchedule.season == data.season)
            .order_by(SupplySchedule.decade_index)
        )
    )
    if len(supply_rows) != 36 or {row.decade_index for row in supply_rows} != set(range(36)):
        raise ProblemError(422, "Incomplete supply schedule",
                           "Enter available supply for all 36 decades before coordination")
    simulated_farm_ids = {simulation.farm_id for simulation in data.simulations}
    if len(simulated_farm_ids) != len(data.simulations):
        raise ProblemError(422, "Duplicate farms", "A farm can be included only once")
    right_rows = list(db.scalars(
        select(WaterRight)
        .join(Farm, Farm.id == WaterRight.farm_id)
        .where(
            WaterRight.canal_id == canal.id,
            WaterRight.season == data.season,
            Farm.consent_canal_plan.is_(True),
        )
    ))
    rights = {right.farm_id: right for right in right_rows}
    if len(rights) != len(right_rows):
        raise ProblemError(409, "Duplicate water rights",
                           "A farm has more than one water right for this canal and season")
    farm_names = {
        farm.id: farm.name
        for farm in db.scalars(select(Farm).where(Farm.id.in_(simulated_farm_ids)))
    }
    if set(rights) != simulated_farm_ids:
        missing = sorted(str(farm_id) for farm_id in simulated_farm_ids - set(rights))
        unmodeled = sorted(str(farm_id) for farm_id in set(rights) - simulated_farm_ids)
        details = []
        if missing:
            details.append("No water right is registered for: " + ", ".join(missing))
        if unmodeled:
            details.append(
                "Missing simulation for farms with water rights: " + ", ".join(unmodeled)
            )
        raise ProblemError(422, "Incomplete farm simulations", "; ".join(details))
    if set(farm_names) != simulated_farm_ids:
        raise ProblemError(
            422, "Unknown farm", "A simulation references a farm that does not exist"
        )

    efficiency = canal.conveyance_efficiency
    if not 0 < efficiency <= 1:
        raise ProblemError(
            422, "Invalid conveyance efficiency", "Canal efficiency must be positive"
        )
    farm_demands: list[FarmDemand] = []
    for simulation in data.simulations:
        right = rights[simulation.farm_id]
        options = tuple(
            ShiftOption(
                shift_days=option.shift_days,
                demand_m3_by_decade=tuple(value / efficiency
                                          for value in option.demand_m3_by_decade),
                income_loss_som=option.income_loss_som,
            )
            for option in simulation.shift_options
        )
        farm_demands.append(
            FarmDemand(
                farm_id=str(simulation.farm_id),
                demand_m3_by_decade=tuple(value / efficiency
                                          for value in simulation.demand_m3_by_decade),
                water_right_m3=_water_right_m3(right),
                expected_income_som=simulation.expected_income_som,
                # The simulator's marginal income loss is per m³ at the farm
                # intake; the optimizer works in m³ at the canal head.
                income_loss_per_m3=simulation.income_loss_per_m3 * efficiency,
                shift_options=options,
            )
        )
    try:
        result = coordinate_canal(
            farm_demands,
            tuple(row.volume_m3 for row in supply_rows),
            max_shifts_per_farm=2,
        )
    except CanalInputError as exc:
        raise ProblemError(422, "Invalid coordination input", str(exc)) from exc
    return result, farm_names, data.simulations


def coordinate_plan(db: Session, canal_id: UUID, data: CoordinatePlanInput) -> CanalPlanRead:
    canal = get_canal(db, canal_id)
    if data.simulations is None:
        simulations, model_version, snapshot_ids = _simulate_canal_farms(
            db, canal, data.season, include_shifts=True
        )
        data = data.model_copy(update={
            "simulations": simulations,
            "water_model_version": data.water_model_version or model_version,
            "snapshot_ids": data.snapshot_ids or snapshot_ids,
        })
    result, farm_names, simulations = _coordinate_input(db, canal, data)
    sim_by_id = {str(item.farm_id): item for item in simulations}

    plan = CanalPlan(canal_id=canal.id, season=data.season, status=CanalPlanStatus.PROPOSED)
    crop_demand_by_decade: dict[str, list[float]] = {}
    final_crop_series: dict[str, dict[str, list[float]]] = {}
    for outcome in result.farmers:
        simulation = sim_by_id[outcome.farm_id]
        crop_series = simulation.crop_demand_m3_by_decade
        if outcome.selected_shift_days:
            selected_option = next(
                option for option in simulation.shift_options
                if option.shift_days == outcome.selected_shift_days
            )
            crop_series = selected_option.crop_demand_m3_by_decade
        final_crop_series[outcome.farm_id] = crop_series
        for crop_code, series in crop_series.items():
            crop_total = crop_demand_by_decade.setdefault(crop_code, [0.0] * 36)
            for decade_index, farm_gate_demand in enumerate(series):
                crop_total[decade_index] += farm_gate_demand / canal.conveyance_efficiency

    plan.summary = {
        "decades": [
            {
                "decade": index + 1,
                "supply_head_m3": result.supply_m3_by_decade[index],
                "demand_head_before_m3": result.demand_before_m3_by_decade[index],
                "demand_head_after_m3": result.demand_after_m3_by_decade[index],
                "deficit_before_m3": result.deficit_before_m3_by_decade[index],
                "deficit_after_m3": result.deficit_after_m3_by_decade[index],
            }
            for index in range(36)
        ],
        "crop_demand_head_m3_by_decade": [
            {
                "decade": index + 1,
                "crops": {
                    crop_code: round(series[index], 3)
                    for crop_code, series in sorted(crop_demand_by_decade.items())
                },
            }
            for index in range(36)
        ],
        "farm_count": len(result.farmers),
        "peak_deficit_before_m3": max(result.deficit_before_m3_by_decade),
        "peak_deficit_after_m3": max(result.deficit_after_m3_by_decade),
        "coordination_gain_percent": round(result.improvement_percent, 2),
        "coordination_useful": result.coordination_useful,
        "fairness_satisfied": result.fairness_feasible,
        "message": (
            "Coordination was not applied because total gains cannot protect every farm"
            if not result.fairness_feasible
            else "Coordination provides less than 2% gain this season"
            if not result.coordination_useful
            else None
        ),
        "conveyance_efficiency": canal.conveyance_efficiency,
        "water_model_version": data.water_model_version or "unknown",
        "snapshot_ids": data.snapshot_ids,
        "source": "water_simulation",
    }
    db.add(plan)
    db.flush()
    for outcome in result.farmers:
        simulation = sim_by_id[outcome.farm_id]
        water_by_decade = [
            {
                "decade": index + 1,
                "allocated_head_m3": round(outcome.assigned_water_m3_by_decade[index], 3),
                "allocated_farm_m3": round(
                    outcome.assigned_water_m3_by_decade[index] * canal.conveyance_efficiency, 3
                ),
            }
            for index in range(36)
        ]
        baseline_farm_water = sum(outcome.baseline_water_m3_by_decade) * canal.conveyance_efficiency
        coordinated_farm_water = (
            sum(outcome.assigned_water_m3_by_decade) * canal.conveyance_efficiency
        )
        db.add(
            CanalProposal(
                canal_plan_id=plan.id,
                farm_id=UUID(outcome.farm_id),
                change={
                    "kind": "shift_sowing" if outcome.selected_shift_days else "keep_plan",
                    "farm_name": farm_names[UUID(outcome.farm_id)],
                    "sowing_date_before": simulation.sowing_date.isoformat(),
                    "sowing_date_after": (
                        simulation.sowing_date.fromordinal(
                            simulation.sowing_date.toordinal() + outcome.selected_shift_days
                        ).isoformat()
                    ),
                    "shift_days": outcome.selected_shift_days,
                    "water_by_decade": water_by_decade,
                    "crop_demand_head_m3_by_decade": {
                        crop_code: [round(value / canal.conveyance_efficiency, 3)
                                    for value in series]
                        for crop_code, series in final_crop_series[outcome.farm_id].items()
                    },
                    "coordination_gain_percent": result.improvement_percent,
                },
                water_delta_m3=coordinated_farm_water - baseline_farm_water,
                income_delta_som=round(
                    outcome.coordinated_income_som - outcome.baseline_income_som
                ),
                compensation_som=round(outcome.compensation_som),
            )
        )
    db.flush()
    # Record plan membership once per farm; the table is keyed by both IDs.
    for farm_id in sorted({UUID(farm_id) for farm_id in sim_by_id}):
        db.execute(
            CanalPlan.__table__.metadata.tables["canal_plan_members"].insert().values(
                canal_plan_id=plan.id, farm_id=farm_id
            )
        )
    db.commit()
    db.refresh(plan)
    return _plan_read(plan)


def _plan_read(plan: CanalPlan) -> CanalPlanRead:
    return CanalPlanRead(
        id=plan.id,
        canal_id=plan.canal_id,
        season=plan.season,
        status=plan.status.value,
        summary=plan.summary,
        proposals=[
            ProposalRead(
                id=proposal.id,
                farm_id=proposal.farm_id,
                change=proposal.change,
                water_delta_m3=proposal.water_delta_m3,
                response=proposal.response,
            )
            for proposal in sorted(plan.proposals, key=lambda item: str(item.farm_id))
        ],
    )


def get_plan(db: Session, plan_id: UUID) -> CanalPlanRead:
    plan = db.get(CanalPlan, plan_id)
    if plan is None:
        raise NotFoundError("Canal plan", plan_id)
    return _plan_read(plan)


def get_latest_demand(db: Session, canal_id: UUID, season: int) -> dict:
    canal = get_canal(db, canal_id)
    plan = db.scalar(
        select(CanalPlan)
        .where(CanalPlan.canal_id == canal_id, CanalPlan.season == season)
        .order_by(CanalPlan.created_at.desc())
        .limit(1)
    )
    if plan is None:
        simulations, model_version, snapshots = _simulate_canal_farms(
            db, canal, season, include_shifts=False
        )
        demand = [sum(sim.demand_m3_by_decade[index] for sim in simulations)
                  / canal.conveyance_efficiency
                  for index in range(36)]
        supply_rows = list(db.scalars(
            select(SupplySchedule).where(
                SupplySchedule.canal_id == canal_id,
                SupplySchedule.season == season,
            )
        ))
        supply = {row.decade_index: row.volume_m3 for row in supply_rows}
        crop_totals: dict[str, list[float]] = {}
        for simulation in simulations:
            for crop_code, series in simulation.crop_demand_m3_by_decade.items():
                total = crop_totals.setdefault(crop_code, [0.0] * 36)
                for index, value in enumerate(series):
                    total[index] += value / canal.conveyance_efficiency
        decades = [
            {
                "decade": index + 1,
                "supply_head_m3": supply.get(index, 0.0),
                "demand_head_before_m3": demand[index],
                "demand_head_after_m3": demand[index],
                "deficit_before_m3": max(0.0, demand[index] - supply.get(index, 0.0)),
                "deficit_after_m3": max(0.0, demand[index] - supply.get(index, 0.0)),
            }
            for index in range(36)
        ]
        return {
            "canal_id": str(canal_id),
            "season": season,
            "status": "not_calculated",
            "decades": decades,
            "crop_demand_head_m3_by_decade": [
                {
                    "decade": index + 1,
                    "crops": {code: round(series[index], 3)
                              for code, series in sorted(crop_totals.items())},
                }
                for index in range(36)
            ],
            "farm_count": len(simulations),
            "peak_deficit_before_m3": max((item["deficit_before_m3"] for item in decades), default=0),
            "peak_deficit_after_m3": max((item["deficit_after_m3"] for item in decades), default=0),
            "water_model_version": model_version,
            "snapshot_ids": snapshots,
            "source": "water_simulation",
        }
    return {
        "canal_id": str(canal_id),
        "season": season,
        "plan_id": str(plan.id),
        "plan_status": plan.status.value,
        **plan.summary,
    }


def respond_to_proposal(db: Session, proposal_id: UUID, response: ProposalResponse,
                        counter_note: str | None) -> dict:
    proposal = db.get(CanalProposal, proposal_id)
    if proposal is None:
        raise NotFoundError("Canal proposal", proposal_id)
    if proposal.response != ProposalResponse.PENDING:
        raise ProblemError(409, "Proposal already answered", "A response was already recorded")
    proposal.response = response
    proposal.counter_note = counter_note.strip() if counter_note else None
    proposal.responded_at = datetime.now(timezone.utc)
    plan = db.get(CanalPlan, proposal.canal_plan_id)
    responses = [item.response for item in plan.proposals]
    if response == ProposalResponse.REJECT or ProposalResponse.REJECT in responses:
        plan.status = CanalPlanStatus.REJECTED
    elif all(item == ProposalResponse.AGREE for item in responses):
        plan.status = CanalPlanStatus.AGREED
    else:
        plan.status = CanalPlanStatus.PROPOSED
    db.commit()
    return {"proposal_id": str(proposal.id), "response": proposal.response.value,
            "plan_status": plan.status.value}
