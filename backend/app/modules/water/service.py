"""Модуль «Вода и климат»: сборка М1–М6 в сезон поля.

Внутренние контракты (вызывают модули стратегий и канала):

    simulate_field(field, crop, sowing_date, scenario, year) -> FieldSeason
    history_years() -> list[int]

Цепочка расчёта (раздел 8 ТЗ):
    снимок NASA POWER -> М1 климат -> М2 ET0 -> М3 Kc, ETc -> М5 очередь полива
    -> М4 суточный баланс корневой зоны -> М6 урожай -> свод по декадам.

Формул здесь нет — они в пакете agroshift_core. Здесь только сборка и агрегирование.
"""

from datetime import date, timedelta
from functools import lru_cache
from typing import Any

import numpy as np

from agroshift_core import MODEL_VERSION
from agroshift_core import climate as m1
from agroshift_core import crop_et as m3
from agroshift_core import irrigation as m5
from agroshift_core import water_balance as m4
from agroshift_core import yield_model as m6
from agroshift_core.calendar import decade_index, decade_indices
from app.modules.water import catalog, climate_store, sources
from app.modules.water.inputs import (
    CropInput,
    FieldInput,
    ScenarioInput,
    WaterInput,
    _month_day,
    pick,
)
from app.modules.water.schemas import (
    Alert,
    ClimateCell,
    ClimateDay,
    ClimateDecadeNorm,
    ClimateResponse,
    DailySeries,
    DataSourcesResponse,
    DecadeWater,
    Ensemble,
    EnsembleDecade,
    FieldInfo,
    FieldSeason,
    FrostDates,
    InputValue,
    Percentiles,
    QCInfo,
    SeasonTotals,
    StageYield,
    WaterBalanceResponse,
    YearSummary,
)

# Допущения, когда вход неизвестен (помечаются в unknown_inputs — «пропуск ≠ ноль»)
DEFAULT_TURN_INTERVAL_DAYS = 10
DEFAULT_TURN_NORM_M3_HA = 700.0     # справочная поливная норма брутто за одну очередь
DEFAULT_RELIABILITY = 0.85
K_FROST_DEFAULT = 0.25              # потеря урожая сада за день заморозка в цветение, оценка
MIN_NEED_FOR_STATUS_MM = 5.0        # меньшая потребность не красит декаду
MIN_SEVERITY_PCT = 5.0              # недобор меньше 5 % — в пределах погрешности, не тревога


def history_years() -> list[int]:
    """30 последних полных лет NASA POWER — выборки для P10/P50/P90 и «было в N из 30 лет»."""
    return climate_store.history_years()


def simulate_field(field: Any, crop: Any, sowing_date: Any, scenario: Any = None,
                   year: int | None = None, *, water: Any = None,
                   daily: bool = False) -> FieldSeason:
    """Сезон поля в погоде исторического года `year`.

    field, crop, scenario — любые объекты с атрибутами из раздела 7.1 ТЗ (см. inputs.py).
    sowing_date — дата сева (для многолетних — начало вегетации); год даты не важен,
                  берутся месяц и день.
    scenario    — None = базовые условия.
    year        — год погоды из history_years(); None = год сценария или последний.
    water       — очередь полива, если её нет в самом field. Не задана — берётся из
                  водных прав хозяйства поля (farms.get_farm), иначе справочная норма.
    daily       — приложить суточные ряды.

    Результат детерминирован и кэшируется: одинаковые входы -> тот же объект.
    """
    if water is None:
        water = sources.farm_water_for(field)
    field_in = FieldInput.from_any(field, water)
    crop_in = CropInput.from_any(crop)
    scenario_in = ScenarioInput.from_any(scenario)
    if year is None:
        year = scenario_in.climate_year or history_years()[-1]
    return _simulate(field_in, crop_in, _month_day(sowing_date, (5, 1)), scenario_in,
                     int(year), bool(daily))


# --------------------------------------------------------------------------- расчёт сезона

def _r(value: float, digits: int = 2) -> float:
    return round(float(value), digits) + 0.0   # + 0.0 убирает «-0.0»


def _percentiles(values) -> Percentiles:
    p10, p50, p90 = np.percentile(np.asarray(values, dtype=float), [10, 50, 90])
    return Percentiles(p10=_r(p10, 3), p50=_r(p50, 3), p90=_r(p90, 3))


def _season_start(sowing: tuple[int, int], year: int) -> date:
    month, day = sowing
    if (month, day) == (2, 29):
        day = 28
    return date(year, month, day)


def _reliability(water: WaterInput, day: date, base: float) -> float:
    if day.month in water.failure_months:
        return water.failure_reliability
    if isinstance(water.reliability, tuple):
        return water.reliability[decade_index(day) - 1]
    return base


def _turns(field: FieldInput, scenario: ScenarioInput, eta_field: float, start: date, n: int,
           inputs: dict[str, InputValue], unknown: list[str]):
    """М5: очередь полива -> по дням сезона: доступно нетто (мм), подано брутто (м³),
    число плановых и сорванных очередей."""
    available = np.zeros(n)
    supplied = np.zeros(n)
    planned = np.zeros(n, dtype=int)
    failed = np.zeros(n, dtype=int)
    water = field.water
    if field.irrigation_method == "none":
        return available, supplied, planned, failed

    interval = water.turn_interval_days or DEFAULT_TURN_INTERVAL_DAYS
    if water.turn_hours is not None and water.flow_l_s is not None:
        fixed_volume = m5.turn_volume_m3(water.turn_hours, water.flow_l_s) * water.share
        source = field.source_of("water")
    elif water.limit_m3 is not None:
        fixed_volume = None           # лимит делится поровну на очереди сезона
        source = field.source_of("water")
    else:
        fixed_volume = DEFAULT_TURN_NORM_M3_HA * field.area_ha
        source = "unknown"
        unknown.append("water_limit")
    if water.turn_interval_days is None and "water_limit" not in unknown:
        unknown.append("water_limit")

    if water.reliability is None and not water.failure_months:
        base_reliability, rel_source = DEFAULT_RELIABILITY, "unknown"
        unknown.append("water_reliability")
    else:
        base_reliability = (water.reliability if isinstance(water.reliability, float)
                            else DEFAULT_RELIABILITY if water.reliability is None else 1.0)
        rel_source = field.source_of("water_reliability")

    end = start + timedelta(days=n - 1)
    volume_for_report = fixed_volume
    for cal_year in range(start.year, end.year + 1):
        shift = timedelta(days=scenario.supply_shift_days)
        first = (date(cal_year, *water.season_start) + shift
                 + timedelta(days=water.turn_offset_days))
        last = date(cal_year, *water.season_end) + shift
        n_turns = max(0, (last - first).days // interval + 1)
        if n_turns == 0:
            continue
        days = [first + timedelta(days=k * interval) for k in range(n_turns)]
        volume = fixed_volume if fixed_volume is not None else (
            water.limit_m3 * water.share / n_turns)
        volume_for_report = volume
        reliability = [_reliability(water, d, base_reliability) for d in days]
        is_failed = m5.failed_turns(n_turns, reliability, scenario.seed, cal_year)
        for k, day in enumerate(days):
            offset = (day - start).days
            if not 0 <= offset < n:
                continue
            planned[offset] += 1
            if is_failed[k]:
                failed[offset] += 1
                continue
            factor = scenario.water_supply_factor
            if scenario.water_supply_months and day.month not in scenario.water_supply_months:
                factor = 1.0
            supplied[offset] += volume * factor
            available[offset] += float(
                m5.net_irrigation_mm(volume * factor, eta_field, field.area_ha))

    inputs["turn_interval_days"] = InputValue(
        value=interval, unit="day",
        source_type=source if water.turn_interval_days is not None else "unknown")
    inputs["turn_volume_m3"] = InputValue(value=_r(volume_for_report or 0.0, 1), unit="m3",
                                          source_type=source)
    inputs["water_reliability"] = InputValue(value=base_reliability, source_type=rel_source,
                                             range=(0.0, 1.0))
    return available, supplied, planned, failed


@lru_cache(maxsize=8192)
def _simulate(field: FieldInput, crop: CropInput, sowing: tuple[int, int],
              scenario: ScenarioInput, year: int, daily: bool) -> FieldSeason:
    inputs: dict[str, InputValue] = {}
    unknown: list[str] = []

    # --- М1 + М2: климат ячейки NASA POWER, приведённый к полю ---
    meta = climate_store.nearest_snapshot(field.lat, field.lon)
    if field.lat is None or field.lon is None:
        unknown.append("location")
    if field.elevation_m is None:
        unknown.append("elevation")
    inputs["elevation_m"] = InputValue(
        value=field.elevation_m if field.elevation_m is not None else meta["cell_elevation_m"],
        unit="m",
        source_type=field.source_of("elevation_m") if field.elevation_m is not None
        else "unknown")
    clim = climate_store.prepared_climate(
        meta["code"],
        round(field.lat if field.lat is not None else meta["lat"], 2),
        None if field.elevation_m is None else float(round(field.elevation_m)),
        round(scenario.temp_delta_c, 2),
        round(scenario.precip_factor, 3),
    )
    start = _season_start(sowing, year)
    first_day, last_day = clim.start, clim.start + timedelta(days=clim.n - 1)
    if not first_day <= start <= last_day:
        raise ValueError(f"год {year} вне снимка NASA POWER ({first_day.year}–{last_day.year})")

    # --- М3: стадии, Kc, ETc ---
    if crop.gdd_required:
        span = clim.season_index(start, int(sum(crop.stage_days) * 1.4) + 1)
        gdd = m1.gdd_daily(clim.tmax[span], clim.tmin[span], crop.t_base)
        lengths = m3.stage_lengths_from_gdd(gdd, crop.stage_days, crop.gdd_required)
    else:
        lengths = crop.stage_days
    n = int(sum(lengths))
    idx = clim.season_index(start, n)
    dates = np.datetime64(start) + np.arange(n)
    stage = m3.stage_index(lengths)
    et0, precip = clim.et0[idx], clim.precip[idx]
    tmax, tmin = clim.tmax[idx], clim.tmin[idx]

    kc_mid, kc_end = crop.kc_mid, crop.kc_end
    if crop.height_m:
        mid = stage == 2
        kc_mid = m3.adjust_kc_for_climate(crop.kc_mid, clim.ws2m[idx][mid].mean(),
                                          clim.rh_min[idx][mid].mean(), crop.height_m)
        if crop.kc_end > 0.45:
            late = stage == 3
            kc_end = m3.adjust_kc_for_climate(crop.kc_end, clim.ws2m[idx][late].mean(),
                                              clim.rh_min[idx][late].mean(), crop.height_m)
    kc = m3.kc_curve(lengths, crop.kc_ini, kc_mid, kc_end)
    etc = m3.crop_et(et0, kc)

    # --- почва ---
    if field.taw_mm_per_m is not None:
        taw_per_m, taw_source = field.taw_mm_per_m, field.source_of("taw_mm_per_m")
    elif field.soil_type in m4.TAW_MM_PER_M:
        taw_per_m, taw_source = m4.TAW_MM_PER_M[field.soil_type], "reference"
    else:
        taw_per_m, taw_source = m4.TAW_MM_PER_M_DEFAULT, "unknown"
        unknown.append("taw")
    inputs["taw_mm_per_m"] = InputValue(value=taw_per_m, unit="mm/m", source_type=taw_source,
                                        range=(80.0, 200.0))
    root_depth = m3.root_depth_curve(lengths, crop.root_depth_m, crop.is_perennial)
    taw = m4.total_available_water(taw_per_m, root_depth)
    runoff = m4.scs_runoff(precip, m4.curve_number(field.soil_type, field.slope_deg))
    f0 = field.initial_depletion_fraction
    inputs["initial_depletion_fraction"] = InputValue(value=f0, source_type="reference",
                                                      range=(0.0, 1.0))

    # --- М5: КПД и очередь ---
    eff_range = m5.field_efficiency_range(field.irrigation_method)
    if field.eta_field is not None:
        eta_field, eta_source = field.eta_field, field.source_of("eta_field", "measured")
    else:
        eta_field, eta_source = m5.default_field_efficiency(field.irrigation_method), "reference"
    inputs["field_efficiency"] = InputValue(value=eta_field, source_type=eta_source,
                                            range=eff_range)
    if field.water.conveyance_efficiency is not None:
        eta_conv, conv_source = (field.water.conveyance_efficiency,
                                 field.source_of("conveyance_efficiency"))
    else:
        eta_conv, conv_source = m5.default_conveyance_efficiency(), "unknown"
        unknown.append("canal_efficiency")
    inputs["canal_efficiency"] = InputValue(value=eta_conv, source_type=conv_source,
                                            range=m5.CONVEYANCE_EFFICIENCY_RANGE)
    available, supplied, planned, failed = _turns(field, scenario, eta_field, start, n,
                                                  inputs, unknown)

    # --- М4: суточный баланс корневой зоны ---
    balance = m4.simulate_root_zone(etc, precip, taw, crop.p_depletion, f0 * float(taw[0]),
                                    runoff=runoff, irrigation_available=available,
                                    new_soil_depletion=f0)

    # --- М6: урожай ---
    if crop.ky_stages:
        f_water, details = m6.water_factor_by_stage(balance.eta, etc, stage, crop.ky_stages)
    else:
        f_water = m6.water_factor_seasonal(balance.eta, etc, crop.ky)
        _, details = m6.water_factor_by_stage(balance.eta, etc, stage, (crop.ky,) * 4)
    alerts: list[Alert] = []

    f_heat = 1.0
    if crop.t_crit_heat is not None:
        # фаза цветения — первая треть середины сезона (экспертное допущение)
        flower_start = lengths[0] + lengths[1]
        flower = slice(flower_start, flower_start + max(7, lengths[2] // 3))
        hot_in_flower = int((tmax[flower] > crop.t_crit_heat).sum())
        f_heat = m6.heat_factor(hot_in_flower, crop.k_heat)
        if hot_in_flower:
            alerts.append(Alert(type="heat_in_flowering", days=hot_in_flower,
                                decade=int(decade_indices(dates[flower])[0]),
                                value=_r(1.0 - f_heat, 3)))

    f_frost = 1.0
    if crop.t_min_kill is not None:
        if crop.is_perennial:
            window = slice(lengths[0] // 2, lengths[0] + 14)      # цветение сада
        else:
            window = slice(7, lengths[0])                         # всходы однолетних
        frost_mask = tmin[window] < crop.t_min_kill
        frost_days = int(frost_mask.sum())
        if frost_days:
            first_frost = dates[window][np.argmax(frost_mask)]
            frost_decade = int(decade_indices(np.array([first_frost]))[0])
            if crop.is_perennial:
                f_frost = m6.frost_factor(frost_days, crop.k_frost or K_FROST_DEFAULT)
                alerts.append(Alert(type="frost_in_bloom", days=frost_days,
                                    decade=frost_decade, value=_r(1.0 - f_frost, 3)))
            else:
                alerts.append(Alert(type="resow_risk", days=frost_days, decade=frost_decade))

    multiplier = m6.relative_yield(f_water, f_heat, f_frost)
    yield_t_ha = (None if crop.yield_potential_t_ha is None
                  else m6.round_yield(crop.yield_potential_t_ha * multiplier))

    # --- свод по декадам ---
    dec = decade_indices(dates)
    cuts = np.flatnonzero(np.diff(dec)) + 1
    starts = np.concatenate(([0], cuts))
    ends = np.concatenate((cuts, [n]))

    def total(arr):
        return np.add.reduceat(np.asarray(arr, dtype=float), starts)

    eff_rain = precip - balance.runoff - balance.dp_rain
    s_et0, s_etc, s_eta = total(et0), total(etc), total(balance.eta)
    s_p, s_eff, s_ro, s_dp = total(precip), total(eff_rain), total(balance.runoff), total(
        balance.dp)
    s_irr, s_supplied = total(balance.irrigation), total(supplied)
    s_planned, s_failed = total(planned), total(failed)
    s_ks, s_hot = total(balance.ks), total(tmax > m1.HOT_DAY_TMAX_C)
    need_net = np.maximum(s_etc - s_eff, 0.0)
    need_gross = m5.gross_volume_m3(need_net, eta_field, field.area_ha)
    used = m5.gross_volume_m3(s_irr, eta_field, field.area_ha)
    # дефицит — нехватка поданной воды, а не «почва не приняла»: сравниваем потребность
    # с тем, что очередь принесла к корням (пример 15.2: 300 мм × 0,5 = 150 мм)
    received_net = m5.net_irrigation_mm(s_supplied, eta_field, field.area_ha)
    deficit_mm = np.maximum(need_net - received_net, 0.0)
    deficit_m3 = m5.gross_volume_m3(deficit_mm, eta_field, field.area_ha)
    with np.errstate(divide="ignore", invalid="ignore"):
        deficit_pct = np.where(need_net > 0, deficit_mm / need_net * 100.0, 0.0)

    decades: list[DecadeWater] = []
    for i, (a, b) in enumerate(zip(starts, ends, strict=True)):
        # Обводка поля: пока почва держит запас (D_r <= RAW), нехватка подачи — ещё не
        # беда. Тревога — когда запас исчерпан или культура уже недобирает (пример 15.1).
        stress = (1.0 - s_eta[i] / s_etc[i]) * 100.0 if s_etc[i] > 0 else 0.0
        buffer_gone = balance.dr[b - 1] > balance.raw[b - 1]
        shortfall = (deficit_pct[i]
                     if buffer_gone and need_net[i] >= MIN_NEED_FOR_STATUS_MM else 0.0)
        severity = max(stress, shortfall)
        if severity < MIN_SEVERITY_PCT:
            status = "ok"
        elif severity < 20.0:
            status = "deficit_lt20"
        else:
            status = "deficit_ge20"
            alerts.append(Alert(type="water_deficit", decade=int(dec[a]),
                                value=_r(severity, 1)))
        decades.append(DecadeWater(
            decade=int(dec[a]),
            start=dates[a].astype(object), end=dates[b - 1].astype(object), days=int(b - a),
            stage=m3.STAGES[int(np.bincount(stage[a:b], minlength=4).argmax())],
            et0_mm=_r(s_et0[i]), etc_mm=_r(s_etc[i]), eta_mm=_r(s_eta[i]),
            precip_mm=_r(s_p[i]), eff_precip_mm=_r(s_eff[i]), runoff_mm=_r(s_ro[i]),
            deep_percolation_mm=_r(s_dp[i]), irrigation_net_mm=_r(s_irr[i]),
            need_net_mm=_r(need_net[i]), need_gross_m3=_r(need_gross[i], 1),
            gross_mm=_r(need_net[i] / eta_field),
            need_head_m3=_r(need_gross[i] / eta_conv, 1),
            received_m3=_r(s_supplied[i], 1), used_m3=_r(used[i], 1),
            deficit_mm=_r(deficit_mm[i]), deficit_m3=_r(deficit_m3[i], 1),
            deficit_pct=_r(deficit_pct[i], 1), stress_pct=_r(stress, 1),
            ks_avg=_r(s_ks[i] / (b - a), 3),
            dr_end_mm=_r(balance.dr[b - 1]), raw_mm=_r(balance.raw[b - 1]),
            taw_mm=_r(balance.taw[b - 1]),
            turns_planned=int(s_planned[i]), turns_failed=int(s_failed[i]),
            hot_days=int(s_hot[i]), status=status,
        ))

    total_need = float(need_net.sum())
    totals = SeasonTotals(
        et0_mm=_r(s_et0.sum()), etc_mm=_r(s_etc.sum()), eta_mm=_r(s_eta.sum()),
        precip_mm=_r(s_p.sum()), eff_precip_mm=_r(s_eff.sum()),
        irrigation_net_mm=_r(s_irr.sum()), need_net_mm=_r(total_need),
        need_gross_m3=_r(need_gross.sum(), 1), need_head_m3=_r(need_gross.sum() / eta_conv, 1),
        received_m3=_r(s_supplied.sum(), 1), used_m3=_r(used.sum(), 1),
        deficit_m3=_r(deficit_m3.sum(), 1),
        deficit_pct=_r(deficit_mm.sum() / total_need * 100.0 if total_need > 0 else 0.0, 1),
    )
    worst = int(dec[starts[int(np.argmax(deficit_m3))]]) if deficit_m3.max() > 0 else None

    series = None
    if daily:
        series = DailySeries(
            dates=[d.astype(object) for d in dates],
            et0=np.round(et0, 2).tolist(), etc=np.round(etc, 2).tolist(),
            eta=np.round(balance.eta, 2).tolist(), precip=np.round(precip, 2).tolist(),
            irrigation=np.round(balance.irrigation, 2).tolist(),
            dr=np.round(balance.dr, 2).tolist(), raw=np.round(balance.raw, 2).tolist(),
            taw=np.round(balance.taw, 2).tolist(), ks=np.round(balance.ks, 3).tolist(),
        )

    return FieldSeason(
        field_id=field.id, crop_code=crop.code, year=year,
        sowing_date=start, harvest_date=start + timedelta(days=n - 1), season_days=n,
        stage_days=lengths, area_ha=field.area_ha,
        decades=decades,
        stages=[StageYield(stage=m3.STAGES[d.stage], days=d.days, etc_mm=_r(d.etc_mm),
                           eta_mm=_r(d.eta_mm), ratio=_r(d.ratio, 4), ky=d.ky,
                           factor=_r(d.factor, 4)) for d in details],
        totals=totals, worst_decade=worst,
        yield_multiplier=_r(multiplier, 4), f_water=_r(f_water, 4), f_heat=_r(f_heat, 4),
        f_frost=_r(f_frost, 4),
        yield_potential_t_ha=crop.yield_potential_t_ha, yield_t_ha=yield_t_ha,
        alerts=alerts, balance_error_mm=_r(balance.closure_error(precip), 4),
        completeness="partial" if unknown else "complete",
        unknown_inputs=sorted(set(unknown)), inputs=inputs,
        snapshots=[meta["code"]], model_version=MODEL_VERSION, et0_method=clim.et0_method,
        kc_used=(_r(crop.kc_ini, 3), _r(kc_mid, 3), _r(kc_end, 3)),
        daily=series,
    )


# --------------------------------------------------------------------------- эндпоинты

def _cell(meta: dict) -> ClimateCell:
    cell = meta["grid_cell"]
    return ClimateCell(snapshot=meta["code"], point_name=meta.get("name_ru") or meta.get("name"),
                       center=tuple(cell["center"]), bbox=tuple(cell["bbox"]),
                       cell_elevation_m=_r(meta["cell_elevation_m"], 1))


def _ensemble(seasons: list[FieldSeason]) -> Ensemble:
    decade_ids = sorted({d.decade for s in seasons for d in s.decades},
                        key=lambda k: min(i for s in seasons for i, d in enumerate(s.decades)
                                          if d.decade == k))
    by_decade: list[EnsembleDecade] = []
    for k in decade_ids:
        rows = [next((d for d in s.decades if d.decade == k), None) for s in seasons]
        by_decade.append(EnsembleDecade(
            decade=k,
            need_gross_m3=_percentiles([r.need_gross_m3 if r else 0.0 for r in rows]),
            received_m3=_percentiles([r.received_m3 if r else 0.0 for r in rows]),
            deficit_pct=_percentiles([r.deficit_pct if r else 0.0 for r in rows]),
            years_deficit_ge20=sum(1 for r in rows if r and r.status == "deficit_ge20"),
        ))
    yields = [s.yield_t_ha for s in seasons]
    return Ensemble(
        years=[s.year for s in seasons],
        yield_multiplier=_percentiles([s.yield_multiplier for s in seasons]),
        yield_t_ha=None if any(y is None for y in yields) else Percentiles(
            **{k: round(v, 1) for k, v in _percentiles(yields).model_dump().items()}),
        need_gross_m3=_percentiles([s.totals.need_gross_m3 for s in seasons]),
        deficit_m3=_percentiles([s.totals.deficit_m3 for s in seasons]),
        decades=by_decade,
        per_year=[YearSummary(year=s.year, yield_multiplier=s.yield_multiplier,
                              deficit_m3=s.totals.deficit_m3, worst_decade=s.worst_decade)
                  for s in seasons],
    )


def get_field_water_balance(field_id: str, strategy: str | None = None,
                            scenario: str | None = None, year: int | None = None,
                            daily: bool = False) -> WaterBalanceResponse:
    """GET /fields/{id}/water-balance — водный баланс поля по декадам (М4–М6)."""
    context = sources.get_field_context(field_id)
    scenario_in = ScenarioInput.from_any(sources.resolve_scenario(scenario))
    field = FieldInput.from_any(context.field, context.water)
    crop, sowing = CropInput.from_any(context.crop), context.sowing

    years = history_years()
    plan = sources.resolve_strategy_crop(strategy, field_id, year or years[-1])
    if plan is not None:
        crop = CropInput.from_any(pick(plan, "crop", default=context.crop))
        sowing = _month_day(pick(plan, "sowing_date"), sowing)

    seasons = [_simulate(field, crop, sowing, scenario_in, y, False) for y in years]
    if year is not None:
        mode = "requested"
    elif scenario_in.climate_year is not None:
        year, mode = scenario_in.climate_year, "scenario"
    else:
        # «типичный год» — медианный по урожаю (при равенстве — по дефициту воды)
        ranked = sorted(seasons, key=lambda s: (s.yield_multiplier, -s.totals.deficit_m3,
                                                s.year))
        year, mode = ranked[len(ranked) // 2].year, "median"

    season = _simulate(field, crop, sowing, scenario_in, int(year), bool(daily))
    meta = climate_store.nearest_snapshot(field.lat, field.lon)
    return WaterBalanceResponse(
        field=FieldInfo(
            id=field.id, name=field.name, farm_id=context.farm_id, farm_name=context.farm_name,
            area_ha=field.area_ha, lat=field.lat, lon=field.lon, elevation_m=field.elevation_m,
            soil_type=field.soil_type, irrigation_method=field.irrigation_method,
            crop_code=crop.code, crop_name=crop.name, sowing_date=season.sowing_date,
            source=context.source,
        ),
        cell=_cell(meta), strategy=strategy, scenario=scenario, year=int(year), year_mode=mode,
        season=season, ensemble=_ensemble(seasons),
    )


def get_field_climate(field_id: str, date_from: date | None = None,
                      date_to: date | None = None) -> ClimateResponse:
    """GET /fields/{id}/climate — климат поля из снимка NASA POWER + ET0 (М1–М2)."""
    context = sources.get_field_context(field_id)
    field = FieldInput.from_any(context.field, context.water)
    meta = climate_store.nearest_snapshot(field.lat, field.lon)
    clim = climate_store.prepared_climate(
        meta["code"], round(field.lat if field.lat is not None else meta["lat"], 2),
        None if field.elevation_m is None else float(round(field.elevation_m)))

    years = history_years()
    date_from = date_from or date(years[-1], 1, 1)
    date_to = date_to or date(years[-1], 12, 31)
    first_day, last_day = clim.start, clim.start + timedelta(days=clim.n - 1)
    if date_from > date_to:
        raise ValueError("from должен быть не позже to")
    if date_from < first_day or date_to > last_day:
        raise ValueError(f"период вне снимка NASA POWER: {first_day} — {last_day}")

    a, b = clim.index_of(date_from), clim.index_of(date_to) + 1
    days = [
        ClimateDay(date=clim.dates[i].astype(object), tmax=_r(clim.tmax[i]),
                   tmin=_r(clim.tmin[i]), tmean=_r(clim.tmean[i]), precip=_r(clim.precip[i]),
                   rs=_r(clim.rs[i]), ws2m=_r(clim.ws2m[i]), rh_min=_r(clim.rh_min[i], 1),
                   et0=_r(clim.et0[i]), et0_method="hs" if clim.hargreaves[i] else "pm")
        for i in range(a, b)
    ]

    h0, h1 = clim.index_of(date(years[0], 1, 1)), clim.index_of(date(years[-1], 12, 31)) + 1
    norms = m1.decade_norms(clim.dates[h0:h1], sums={"et0": clim.et0[h0:h1],
                                                     "precip": clim.precip[h0:h1]},
                            means={"tmean": clim.tmean[h0:h1]}, tmax=clim.tmax[h0:h1])
    decade_norms = [
        ClimateDecadeNorm(
            decade=int(row.decade),
            et0_mm=Percentiles(p10=_r(row.et0_p10, 1), p50=_r(row.et0_p50, 1),
                               p90=_r(row.et0_p90, 1)),
            precip_mm=Percentiles(p10=_r(row.precip_p10, 1), p50=_r(row.precip_p50, 1),
                                  p90=_r(row.precip_p90, 1)),
            tmean_c=Percentiles(p10=_r(row.tmean_p10, 1), p50=_r(row.tmean_p50, 1),
                                p90=_r(row.tmean_p90, 1)),
            hot_days_mean=_r(row.hot_days_mean, 2),
        )
        for row in norms.itertuples()
    ]
    frost = [FrostDates(year=y, **v)
             for y, v in m1.frost_dates(clim.dates[a:b], clim.tmin[a:b]).items()]

    qc = clim.qc
    return ClimateResponse(
        field_id=field.id, cell=_cell(meta), date_from=date_from, date_to=date_to,
        field_elevation_m=field.elevation_m,
        temperature_shift_c=_r(clim.temperature_shift_c, 2), et0_method=clim.et0_method,
        days=days, decade_norms=decade_norms, frost=frost, history_years=years,
        qc=QCInfo(days=qc.n_days, missing=sum(qc.missing.values()),
                  out_of_range=sum(qc.out_of_range.values()),
                  interpolated=sum(qc.interpolated.values()),
                  filled_with_norm=sum(qc.climatology.values())),
        model_version=MODEL_VERSION, attribution=catalog.ATTRIBUTION,
    )


def get_data_sources(lang: str = "ru") -> DataSourcesResponse:
    """GET /data-sources — наборы NASA, снимки, атрибуция, ограничения разрешения (FR-11.2)."""
    metas = climate_store.snapshot_metas()
    return DataSourcesResponse(
        attribution=catalog.ATTRIBUTION, model_version=MODEL_VERSION,
        offline_ready=bool(metas),
        datasets=catalog.datasets(lang, metas, _cell),
    )
