"""M15: deterministic canal-demand coordination for the hackathon MVP.

Hydrology and crop-income estimates are supplied by the water/strategy modules. This
module only aggregates those estimates and chooses among pre-simulated sowing shifts.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class ShiftOption:
    """A sowing-date alternative already simulated by the water/economy modules."""

    shift_days: int
    demand_m3_by_decade: tuple[float, ...]
    income_loss_som: float


@dataclass(frozen=True, slots=True)
class FarmDemand:
    farm_id: str
    demand_m3_by_decade: tuple[float, ...]
    water_right_m3: float
    expected_income_som: float
    income_loss_per_m3: float
    shift_options: tuple[ShiftOption, ...] = ()


@dataclass(frozen=True, slots=True)
class FarmCoordination:
    farm_id: str
    demand_m3_by_decade: tuple[float, ...]
    baseline_water_m3_by_decade: tuple[float, ...]
    assigned_water_m3_by_decade: tuple[float, ...]
    baseline_income_som: float
    coordinated_income_som: float
    compensation_som: float
    selected_shift_days: int
    shift_loss_som: float


@dataclass(frozen=True, slots=True)
class CoordinationResult:
    supply_m3_by_decade: tuple[float, ...]
    demand_before_m3_by_decade: tuple[float, ...]
    demand_after_m3_by_decade: tuple[float, ...]
    deficit_before_m3_by_decade: tuple[float, ...]
    deficit_after_m3_by_decade: tuple[float, ...]
    total_income_before_som: float
    total_income_after_som: float
    improvement_percent: float
    coordination_useful: bool
    fairness_feasible: bool
    farmers: tuple[FarmCoordination, ...]
    unserved_demand_m3_by_decade: tuple[float, ...]


class CanalInputError(ValueError):
    """Raised when a canal plan contains invalid or inconsistent input data."""


def _validate_vector(name: str, values: tuple[float, ...], length: int | None = None) -> None:
    if not values:
        raise CanalInputError(f"{name} must not be empty")
    if length is not None and len(values) != length:
        raise CanalInputError(f"{name} must contain {length} decades")
    if any(not isfinite(value) or value < 0 for value in values):
        raise CanalInputError(f"{name} values must be finite and non-negative")


def _aggregate(farms: list[FarmDemand]) -> tuple[float, ...]:
    count = len(farms[0].demand_m3_by_decade)
    return tuple(
        sum(farm.demand_m3_by_decade[index] for farm in farms)
        for index in range(count)
    )


def _allocate_pro_rata(
    demands: list[tuple[float, ...]], rights: list[float], supply: tuple[float, ...]
) -> list[list[float]]:
    """Allocate each decade by legal water rights, capping at actual demand."""
    allocated = [[0.0] * len(supply) for _ in demands]
    for decade, available in enumerate(supply):
        remaining = available
        eligible = {i for i, row in enumerate(demands) if row[decade] > 0}
        while remaining > 1e-9 and eligible:
            total_rights = sum(rights[i] for i in eligible)
            if total_rights <= 0:
                break
            capped: set[int] = set()
            proposed = {i: remaining * rights[i] / total_rights for i in eligible}
            for i in eligible:
                unmet = demands[i][decade] - allocated[i][decade]
                if proposed[i] >= unmet:
                    allocated[i][decade] += unmet
                    remaining -= unmet
                    capped.add(i)
            if capped:
                eligible -= capped
                continue
            for i, amount in proposed.items():
                allocated[i][decade] += amount
            remaining = 0.0
    return allocated


def _income_after_water(
    potential_income_som: float,
    income_loss_per_m3: float,
    demand: tuple[float, ...],
    assigned: tuple[float, ...],
) -> float:
    unmet = sum(
        max(0.0, needed - received)
        for needed, received in zip(demand, assigned, strict=True)
    )
    return max(0.0, potential_income_som - unmet * income_loss_per_m3)


def coordinate_canal(
    farms: list[FarmDemand], supply_m3_by_decade: tuple[float, ...], *, max_shifts_per_farm: int = 2
) -> CoordinationResult:
    """Coordinate pre-simulated crop demand using greedy loss-per-m³ sowing shifts.

    The proportional-rights allocation is the fairness baseline. The greedy MVP
    repeatedly selects the shift with the lowest income-loss / deficit-relief ratio.
    It stops when all decade constraints are satisfied or no supplied alternative
    reduces total unmet demand. Income transfers are zero-sum and are applied only
    when the generated savings can keep every farm at or above its baseline income.
    """
    if not farms:
        raise CanalInputError("At least one farm is required")
    if max_shifts_per_farm < 0:
        raise CanalInputError("max_shifts_per_farm must be non-negative")
    _validate_vector("supply", supply_m3_by_decade)
    decade_count = len(supply_m3_by_decade)
    if len({farm.farm_id for farm in farms}) != len(farms):
        raise CanalInputError("farm_id values must be unique")
    for farm in farms:
        _validate_vector("farm demand", farm.demand_m3_by_decade, decade_count)
        if not isfinite(farm.water_right_m3) or farm.water_right_m3 < 0:
            raise CanalInputError("water rights must be finite and non-negative")
        if not isfinite(farm.expected_income_som) or farm.expected_income_som < 0:
            raise CanalInputError("expected income must be finite and non-negative")
        if not isfinite(farm.income_loss_per_m3) or farm.income_loss_per_m3 < 0:
            raise CanalInputError("income loss per m³ must be finite and non-negative")
        for option in farm.shift_options:
            if option.shift_days == 0 or abs(option.shift_days) not in (10, 20):
                raise CanalInputError("sowing shifts must be ±10 or ±20 days")
            _validate_vector("shift demand", option.demand_m3_by_decade, decade_count)
            if not isfinite(option.income_loss_som) or option.income_loss_som < 0:
                raise CanalInputError("shift income loss must be finite and non-negative")

    base_demands = [farm.demand_m3_by_decade for farm in farms]
    demand_before = _aggregate(farms)
    deficit_before = tuple(max(0.0, demand - supply)
                           for demand, supply in zip(demand_before, supply_m3_by_decade, strict=True))
    baseline_allocations = _allocate_pro_rata(
        base_demands, [farm.water_right_m3 for farm in farms], supply_m3_by_decade
    )
    baseline_income = [
        _income_after_water(farm.expected_income_som, farm.income_loss_per_m3, base_demands[index],
                            tuple(baseline_allocations[index]))
        for index, farm in enumerate(farms)
    ]

    selected: list[ShiftOption | None] = [None] * len(farms)
    used_shifts = [0] * len(farms)
    current_demands = list(base_demands)
    current_total_deficit = sum(deficit_before)
    while current_total_deficit > 1e-7:
        candidates: list[tuple[float, float, int, ShiftOption, float]] = []
        for farm_index, farm in enumerate(farms):
            if used_shifts[farm_index] >= max_shifts_per_farm:
                continue
            previous_shift = selected[farm_index].shift_days if selected[farm_index] else 0
            options = [
                option for option in farm.shift_options
                if previous_shift == 0 or (
                    option.shift_days * previous_shift > 0
                    and abs(option.shift_days) > abs(previous_shift)
                )
                if (abs(option.shift_days) - abs(previous_shift)) // 10
                <= max_shifts_per_farm - used_shifts[farm_index]
            ]
            for option in options:
                trial = list(current_demands)
                trial[farm_index] = option.demand_m3_by_decade
                trial_total_demand = tuple(sum(row[t] for row in trial)
                                           for t in range(decade_count))
                trial_deficit = sum(max(0.0, trial_total_demand[t] - supply_m3_by_decade[t])
                                    for t in range(decade_count))
                relief = current_total_deficit - trial_deficit
                if relief <= 1e-7:
                    continue
                incremental_loss = option.income_loss_som - (
                    selected[farm_index].income_loss_som if selected[farm_index] else 0.0
                )
                if incremental_loss < -1e-7:
                    raise CanalInputError("shift options must be ordered by cumulative income loss")
                ratio = incremental_loss / relief
                candidates.append((ratio, incremental_loss, farm_index, option, trial_deficit))
        if not candidates:
            break
        _, _, farm_index, option, next_deficit = min(
            candidates, key=lambda item: (item[0], item[1], farms[item[2]].farm_id,
                                           abs(item[3].shift_days))
        )
        previous_magnitude = abs(selected[farm_index].shift_days) if selected[farm_index] else 0
        current_demands[farm_index] = option.demand_m3_by_decade
        selected[farm_index] = option
        used_shifts[farm_index] += (abs(option.shift_days) - previous_magnitude) // 10
        current_total_deficit = next_deficit

    demand_after = tuple(sum(row[t] for row in current_demands) for t in range(decade_count))
    deficit_after = tuple(max(0.0, demand - supply)
                          for demand, supply in zip(demand_after, supply_m3_by_decade, strict=True))
    coordinated_allocations = _allocate_pro_rata(
        current_demands, [farm.water_right_m3 for farm in farms], supply_m3_by_decade
    )
    raw_income = [
        _income_after_water(farm.expected_income_som, farm.income_loss_per_m3,
                            current_demands[index],
                            tuple(coordinated_allocations[index])) -
        (selected[index].income_loss_som if selected[index] else 0.0)
        for index, farm in enumerate(farms)
    ]

    # Protect every participant against the proportional baseline, using zero-sum
    # transfers from farms whose coordinated outcome exceeds that baseline.
    deltas = [raw_income[index] - baseline_income[index] for index in range(len(farms))]
    total_surplus = sum(max(0.0, delta) for delta in deltas)
    total_shortfall = sum(max(0.0, -delta) for delta in deltas)
    compensation = [0.0] * len(farms)
    fairness_feasible = True
    if total_surplus + 1e-7 >= total_shortfall and total_shortfall > 0:
        for index, delta in enumerate(deltas):
            if delta < 0:
                compensation[index] = -delta
        for index, delta in enumerate(deltas):
            if delta > 0:
                contribution = min(delta, total_shortfall)
                compensation[index] = -contribution
                total_shortfall -= contribution
        if abs(sum(compensation)) > 1e-6:
            raise AssertionError("Canal compensation must be zero-sum")
    elif total_shortfall > total_surplus + 1e-7:
        # Do not propose a plan that leaves a participant worse off than the
        # transparent proportional-rights baseline.
        current_demands = list(base_demands)
        selected = [None] * len(farms)
        demand_after = demand_before
        deficit_after = deficit_before
        coordinated_allocations = baseline_allocations
        raw_income = baseline_income
        compensation = [0.0] * len(farms)
        fairness_feasible = False

    outcomes = tuple(
        FarmCoordination(
            farm_id=farm.farm_id,
            demand_m3_by_decade=current_demands[index],
            baseline_water_m3_by_decade=tuple(baseline_allocations[index]),
            assigned_water_m3_by_decade=tuple(coordinated_allocations[index]),
            baseline_income_som=baseline_income[index],
            coordinated_income_som=raw_income[index] + compensation[index],
            compensation_som=compensation[index],
            selected_shift_days=selected[index].shift_days if selected[index] else 0,
            shift_loss_som=selected[index].income_loss_som if selected[index] else 0.0,
        )
        for index, farm in enumerate(farms)
    )
    before_income = sum(baseline_income)
    after_income = sum(row.coordinated_income_som for row in outcomes)
    improvement = (max(0.0, after_income - before_income) / before_income * 100.0
                   if before_income > 0 else 0.0)
    return CoordinationResult(
        supply_m3_by_decade=supply_m3_by_decade,
        demand_before_m3_by_decade=demand_before,
        demand_after_m3_by_decade=demand_after,
        deficit_before_m3_by_decade=deficit_before,
        deficit_after_m3_by_decade=deficit_after,
        total_income_before_som=before_income,
        total_income_after_som=after_income,
        improvement_percent=improvement,
        coordination_useful=improvement >= 2.0,
        fairness_feasible=fairness_feasible,
        farmers=outcomes,
        unserved_demand_m3_by_decade=deficit_after,
    )
