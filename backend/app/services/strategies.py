"""Сервис «Стратегии и деньги»: перебор схем (М11), деньги (М9), корма (М8), стресс-тест
(М12), точка поломки (М13). Все числа — из agroshift_core; здесь только сборка входов,
хранение прогонов и форма ответов API.

Внутренний контракт для ИИ-помощника: get_run_summary(run_id) -> RunSummary.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import date
from typing import NamedTuple

import numpy as np

from agroshift_core import MODEL_VERSION
from agroshift_core.breakpoints import bisect_threshold, historical_frequency, safety_margin
from agroshift_core.cashflow import financing_to_hold, find_cash_gap, gap_probability
from agroshift_core.optimizer import (
    P_GAP_LIMIT,
    P_GAP_RESILIENT,
    enumerate_schemes,
    select_strategies,
    win_share,
)
from agroshift_core.plan_eval import Conditions, Noise, PlanPart, PlanResult, evaluate_plan
from agroshift_core.stress import adaptation_price, neighbours, pick_fix
from agroshift_core.uncertainty import cvar, lognormal_noise, percentiles, result_hash
from app.core.config import get_settings
from app.core.errors import NotFoundError, ProblemError
from app.schemas import strategies as sch
from app.services.strategy_inputs import (
    FarmInputs,
    FieldInfo,
    FieldSims,
    Scn,
    load_inputs,
    stub_year_anomalies,
)

log = logging.getLogger(__name__)

# Версия правил выбора стратегий: входит в ключ кэша прогонов, чтобы после смены правил
# не отдавались сохранённые ответы, посчитанные по-старому. 2 — финансирование сверх лимита.
SELECTION_RULES = 2
PRICE_SIGMA = 0.15  # шум цен продукции между годами (оценка; раздел 8.10 допускает до 0,25)
MILK_SIGMA = 0.05
FEED_SIGMA = 0.15
YIELD_LOSS_LIMIT = 0.25  # порог «потеря урожая на поле» для точки поломки (8.13)
UPROOT_STEP_HA = 1.0  # 14.1: одно решение «выкорчевать 1 га»
ASSUMED_FIELD_EFFICIENCY = 0.55  # для пересчёта дефицита нетто в брутто в индексе водности года
TYPE_ORDER: tuple[str, ...] = ("income", "resilient", "water_light", "user")
_ID_RE = re.compile(r"^[rs]_([0-9a-f]{10})_[a-z_]+$")


class PartSpec(NamedTuple):
    crop_id: str
    area_ha: float
    new_planting: bool
    capex_som: float


Option = tuple[PartSpec, ...]
Scheme = tuple[Option, ...]


def _int(x: float) -> int:
    return int(round(float(x)))


def _pct(x: np.ndarray) -> sch.Percentiles:
    p10, p50, p90 = percentiles(x)
    return sch.Percentiles(p10=_int(p10), p50=_int(p50), p90=_int(p90))


def _scn(s: sch.ScenarioIn) -> Scn:
    return Scn(
        water_supply_factor=s.water_supply_factor,
        supply_shift_days=s.supply_shift_days,
        temp_delta_c=s.temp_delta_c,
        precip_factor=s.precip_factor,
        water_months=tuple(sorted(set(s.water_months))),
        price_factor=s.price_factor,
        price_factors=tuple(sorted(s.price_factors.items())),
        feed_price_factor=s.feed_price_factor,
        payment_delay_days=s.payment_delay_days,
        yield_factor=s.yield_factor,
    )


# ----------------------------------------------------------------------------- движок


class Engine:
    """Хозяйство + выборки + кэш воды. Один на (хозяйство, seed, версия входов)."""

    def __init__(self, inputs: FarmInputs, seed: int) -> None:
        self.inputs = inputs
        self.seed = seed
        self.n = len(inputs.years)
        self.params = {cid: c.params for cid, c in inputs.crops.items()}
        self.options: list[list[Option]] = [self._field_options(f) for f in inputs.fields]
        self.schemes, self.truncated = enumerate_schemes(self.options)
        self._sims: dict[tuple, FieldSims] = {}
        self._lock = threading.Lock()
        price = {
            cid: lognormal_noise(seed, f"price:{cid}", self.n, PRICE_SIGMA)
            for cid in sorted(inputs.crops)
        }
        price["milk"] = lognormal_noise(seed, "price:milk", self.n, MILK_SIGMA)
        # корм дорожает в сухой год (8.10): сухость — потеря урожая текущего плана в этот год
        user_parts = self.parts(self.schemes[0], Scn())
        dry = np.mean([1.0 - p.yield_mult for p in user_parts], axis=0)
        feed = lognormal_noise(seed, "feed", self.n, FEED_SIGMA) * (1.0 + dry - dry.mean())
        self.noise = Noise(price=price, feed=feed)

    def _field_options(self, fld: FieldInfo) -> list[Option]:
        """Варианты для поля; первый — текущий план («Мой вариант»)."""
        crops = self.inputs.crops
        current = crops[fld.crop_id]
        options: list[Option] = [(PartSpec(fld.crop_id, fld.area_ha, False, 0.0),)]
        candidates = [cid for cid in sorted(crops) if crops[cid].plantable and cid != fld.crop_id]
        if current.perennial and not current.plantable:
            # старый сад: оставить целиком или выкорчевать 1 га под однолетнюю культуру
            step = min(UPROOT_STEP_HA, fld.area_ha)
            capex = current.uproot_cost_som_ha * step
            for cid in candidates:
                new = PartSpec(cid, step, True, capex)
                rest = fld.area_ha - step
                keep = (PartSpec(fld.crop_id, rest, False, 0.0),) if rest > 1e-9 else ()
                options.append((*keep, new))
        else:
            options.extend((PartSpec(cid, fld.area_ha, True, 0.0),) for cid in candidates)
        return options

    def sims(self, fld: FieldInfo, crop_id: str, scn: Scn) -> FieldSims:
        key = (fld.id, crop_id, scn.water_key())
        with self._lock:
            hit = self._sims.get(key)
        if hit is None:
            hit = self.inputs.simulate(fld, self.inputs.crops[crop_id], scn)
            with self._lock:
                if len(self._sims) > 4000:
                    self._sims.clear()
                self._sims[key] = hit
        return hit

    def parts(self, scheme: Scheme, scn: Scn) -> list[PlanPart]:
        out = []
        for fld, option in zip(self.inputs.fields, scheme, strict=True):
            for spec in option:
                s = self.sims(fld, spec.crop_id, scn)
                k = 10.0 * spec.area_ha  # 1 мм на 1 га = 10 м³
                out.append(
                    PlanPart(
                        fld.id, spec.crop_id, spec.area_ha, s.yield_mult, s.gross_mm * k,
                        s.deficit_mm * k, spec.new_planting, spec.capex_som,
                    )
                )
        return out

    def run(self, scheme: Scheme, scn: Scn) -> tuple[list[PlanPart], PlanResult]:
        parts = self.parts(scheme, scn)
        cond = Conditions(
            price_factor=scn.price_factor,
            price_factors=dict(scn.price_factors),
            feed_price_factor=scn.feed_price_factor,
            payment_delay_days=scn.payment_delay_days,
            yield_factor=scn.yield_factor,
        )
        return parts, evaluate_plan(parts, self.params, self.inputs.econ, cond, self.noise)

    def rotation_ok(self, scheme: Scheme) -> bool:
        """Текущая культура без права повтора не может остаться на поле ещё на год."""
        for fld, option in zip(self.inputs.fields, scheme, strict=True):
            for spec in option:
                same = not spec.new_planting and spec.crop_id == fld.crop_id
                if same and not self.inputs.crops[spec.crop_id].repeat_allowed:
                    return False
        return True

    def field(self, field_id: str) -> FieldInfo:
        return next(f for f in self.inputs.fields if f.id == field_id)

    # --- представление -------------------------------------------------------------

    def median_cash(self, res: PlanResult) -> np.ndarray:
        return np.percentile(res.cash, 50, axis=0)

    def gap_out(self, res: PlanResult) -> sch.CashGapOut:
        reserve = self.inputs.econ.reserve_som
        gap = find_cash_gap(self.median_cash(res), reserve)
        return sch.CashGapOut(
            first_month=None if gap.first_month is None else gap.first_month + 1,
            worst_month=None if gap.worst_month is None else gap.worst_month + 1,
            depth_som=_int(gap.depth_som),
            financing_needed_som=_int(gap.financing_needed_som),
            probability=round(gap_probability(res.cash, reserve), 3),
        )

    def worst_decade(self, parts: list[PlanPart]) -> sch.WorstDecade | None:
        per_part = np.array([np.percentile(p.deficit_m3, 50, axis=0) for p in parts])
        total = per_part.sum(axis=0)
        d = int(total.argmax())
        if total[d] < 1.0:
            return None
        fld = self.field(parts[int(per_part[:, d].argmax())].field_id)
        return sch.WorstDecade(
            decade=d + 1, deficit_m3=_int(total[d]), field_id=fld.id, field_name=fld.name
        )

    def field_losses(self, parts: list[PlanPart], res: PlanResult) -> list[sch.FieldLoss]:
        median = np.percentile(res.yield_loss, 50, axis=1)
        return [
            sch.FieldLoss(
                field_id=p.field_id, field_name=self.field(p.field_id).name, crop_id=p.crop_id,
                yield_loss=round(float(loss), 3),
            )
            for p, loss in zip(parts, median, strict=True)
        ]

    def unsold(self, res: PlanResult) -> list[sch.Unsold]:
        out = []
        for crop_id, tonnes in res.unsold_t.items():
            median = float(np.percentile(tonnes, 50))
            if median > 0.05:
                out.append(
                    sch.Unsold(
                        crop_id=crop_id, tonnes=round(median, 1),
                        max_volume_t=self.params[crop_id].max_volume_t or 0.0,
                    )
                )
        return out

    def decisions(self, scheme: Scheme) -> list[sch.Decision]:
        out = []
        for fld, option in zip(self.inputs.fields, scheme, strict=True):
            for spec in option:
                crop = self.inputs.crops[spec.crop_id]
                action = "keep"
                if spec.new_planting:
                    action = "uproot_and_sow" if spec.capex_som > 0 else "switch"
                out.append(
                    sch.Decision(
                        field_id=fld.id, field_name=fld.name, crop_id=spec.crop_id,
                        crop_name_ru=crop.name_ru, crop_name_en=crop.name_en,
                        area_ha=spec.area_ha, action=action, capex_som=_int(spec.capex_som),
                    )
                )
        return out

    def describe(self, scheme: Scheme, against: Scheme) -> tuple[str, str]:
        """Одна фраза-суть: чем схема отличается от `against` (FR-4.2)."""
        ru, en = [], []
        for fld, option, old in zip(self.inputs.fields, scheme, against, strict=True):
            if option == old:
                continue
            new = [s for s in option if s.new_planting]
            old_crop = self.inputs.crops[old[-1].crop_id]  # что сейчас на изменяемой части
            if not new:  # возврат к текущей культуре поля
                now = self.inputs.crops[fld.crop_id]
                ru.append(f"«{fld.name}»: оставить как сейчас ({now.name_ru.lower()})")
                en.append(f"“{fld.name}”: keep as now ({now.name_en.lower()})")
                continue
            spec = new[0]
            crop = self.inputs.crops[spec.crop_id]
            if spec.capex_som > 0:
                ru.append(
                    f"«{fld.name}»: выкорчевать {spec.area_ha:g} га, вместо него — "
                    f"{crop.name_ru.lower()}"
                )
                en.append(
                    f"“{fld.name}”: uproot {spec.area_ha:g} ha, replace with "
                    f"{crop.name_en.lower()}"
                )
            else:
                ru.append(
                    f"«{fld.name}», {spec.area_ha:g} га: {old_crop.name_ru.lower()} → "
                    f"{crop.name_ru.lower()}"
                )
                en.append(
                    f"“{fld.name}”, {spec.area_ha:g} ha: {old_crop.name_en.lower()} → "
                    f"{crop.name_en.lower()}"
                )
        if not ru:
            return "Без изменений", "No changes"
        return "; ".join(ru), "; ".join(en)

    def outcome(self, scheme: Scheme, parts: list[PlanPart], res: PlanResult) -> sch.PlanOutcome:
        econ = self.inputs.econ
        p10, p50, _ = percentiles(res.cash)
        purchased_dm = float(np.percentile(res.feed.purchased_dm_kg.sum(axis=1), 50))
        return sch.PlanOutcome(
            income_som=_pct(res.income),
            cash_p10=[_int(v) for v in p10],
            cash_p50=[_int(v) for v in p50],
            cash_gap=self.gap_out(res),
            gross_water_m3=_int(np.percentile(res.gross_m3.sum(axis=1), 50)),
            worst_decade=self.worst_decade(parts),
            field_losses=self.field_losses(parts, res),
            feed_purchase_t=round(purchased_dm / (1000.0 * econ.feed_dm_share), 1),
            feed_purchase_som=_int(np.percentile(res.flows["feed_purchase"].sum(axis=1), 50)),
            unsold=self.unsold(res),
            decisions=self.decisions(scheme),
        )

    def provenance(self) -> sch.Provenance:
        return sch.Provenance(
            model_version=MODEL_VERSION, seed=self.seed, n_samples=self.n,
            years=list(self.inputs.years), inputs_status=dict(self.inputs.status),
            warnings=list(self.inputs.warnings),
        )


# ----------------------------------------------------------------------------- хранилище

_engines: dict[tuple, Engine] = {}
_records: dict[str, dict] = {}
_store_lock = threading.Lock()


def _fingerprint(inputs: FarmInputs) -> str:
    return result_hash(
        {
            "fields": [(f.id, f.area_ha, f.crop_id) for f in inputs.fields],
            "crops": {cid: repr(c.params) for cid, c in sorted(inputs.crops.items())},
            "econ": repr(inputs.econ),
            "years": inputs.years,
            "status": inputs.status,
        }
    )


def _engine(farm_id: str, seed: int) -> Engine:
    inputs = load_inputs(farm_id)
    key = (farm_id, seed, _fingerprint(inputs))
    with _store_lock:
        engine = _engines.get(key)
    if engine is None:
        engine = Engine(inputs, seed)
        with _store_lock:
            if len(_engines) > 16:
                _engines.clear()
            _engines[key] = engine
    return engine


def _path(generation_id: str):
    return get_settings().runs_dir / f"gen_{generation_id}.json"


def _save(record: dict) -> None:
    with _store_lock:
        _records[record["generation_id"]] = record
    try:
        path = _path(record["generation_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    except OSError:
        log.warning("не удалось сохранить прогон на диск — он останется только в памяти")


def _load(generation_id: str) -> dict | None:
    with _store_lock:
        record = _records.get(generation_id)
    if record is None:
        try:
            record = json.loads(_path(generation_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        with _store_lock:
            _records[generation_id] = record
    return record


def _record_for(entity: str, entity_id: str) -> dict:
    match = _ID_RE.match(entity_id)
    record = _load(match.group(1)) if match else None
    if record is None:
        raise NotFoundError(entity, entity_id)
    return record


def _run_context(run_id: str) -> tuple[dict, dict, Engine, Scheme]:
    record = _record_for("Run", run_id)
    run = record["runs"].get(run_id)
    if run is None:
        raise NotFoundError("Run", run_id)
    engine = _engine(record["farm_id"], record["seed"])
    scheme: Scheme = tuple(tuple(PartSpec(*spec) for spec in option) for option in run["scheme"])
    if len(scheme) != len(engine.inputs.fields):
        raise ProblemError(
            409, "Conflict", "Поля хозяйства изменились — постройте варианты будущего заново"
        )
    return record, run, engine, scheme


# ----------------------------------------------------------------------------- М11: генерация


def _metrics(
    engine: Engine, parts: list[PlanPart], res: PlanResult, peak: np.ndarray, win: float | None
) -> sch.StrategyMetrics:
    return sch.StrategyMetrics(
        income_som=_pct(res.income),
        cvar10_som=_int(cvar(res.income)),
        gross_water_m3=_pct(res.gross_m3.sum(axis=1)),
        peak_water_m3=_int(res.gross_m3[:, peak].sum(axis=1).mean()),
        worst_decade=engine.worst_decade(parts),
        cash_gap=engine.gap_out(res),
        investment_som=_int(res.capex_som),
        feed_self_sufficiency=round(float(np.percentile(res.feed.self_sufficiency, 50)), 2),
        feed_purchase_som=_int(np.percentile(res.flows["feed_purchase"].sum(axis=1), 50)),
        max_yield_loss=round(float(np.percentile(res.yield_loss, 50, axis=1).max()), 3),
        unsold=engine.unsold(res),
        win_share=None if win is None else round(win, 2),
    )


def generate(farm_id: str, req: sch.GenerateRequest) -> sch.GenerateResponse:
    """POST /farms/{id}/strategies:generate — перебор схем и выбор по целям (М11)."""
    engine = _engine(farm_id, req.seed)
    scn = _scn(req.scenario)
    generation_id = result_hash(
        [farm_id, _fingerprint(engine.inputs), repr(scn), req.seed, MODEL_VERSION, SELECTION_RULES]
    )[:10]
    cached = _load(generation_id)
    if cached is not None:
        return sch.GenerateResponse.model_validate(cached["response"])

    reserve = engine.inputs.econ.reserve_som
    user_scheme = engine.schemes[0]
    user_parts, user_res = engine.run(user_scheme, scn)
    peak = np.sort(np.argsort(-user_res.gross_m3.mean(axis=0), kind="stable")[:3])

    k = len(engine.schemes)
    mean_income, cvar10, p_gap = np.zeros(k), np.zeros(k), np.zeros(k)
    peak_water, fin10, fin5 = np.zeros(k), np.zeros(k), np.zeros(k)
    for i, scheme in enumerate(engine.schemes):
        _, res = engine.run(scheme, scn)
        mean_income[i] = res.income.mean()
        cvar10[i] = cvar(res.income)
        peak_water[i] = res.gross_m3[:, peak].sum(axis=1).mean()
        # по плохим годам: сколько привлечь, чтобы разрыв был не чаще лимита цели
        fin10[i] = financing_to_hold(res.cash, reserve, P_GAP_LIMIT).amount_som
        fin5[i] = financing_to_hold(res.cash, reserve, P_GAP_RESILIENT).amount_som
        # схемы с нарушением севооборота в оптимизации не участвуют
        p_gap[i] = gap_probability(res.cash, reserve) if engine.rotation_ok(scheme) else np.inf
    selection = select_strategies(
        mean_income, cvar10, p_gap, peak_water, fin10,
        financing_at_limit=fin10, financing_at_resilient=fin5,
    )

    by_scheme: dict[int, list[str]] = {}
    for kind in TYPE_ORDER:
        if kind in selection.chosen:
            by_scheme.setdefault(selection.chosen[kind], []).append(kind)
    results = {i: engine.run(engine.schemes[i], scn) for i in by_scheme}
    shares = win_share(np.array([results[i][1].income for i in by_scheme]))

    strategies: list[sch.StrategyOut] = []
    runs: dict[str, dict] = {}
    for (i, kinds), share in zip(by_scheme.items(), shares, strict=True):
        scheme = engine.schemes[i]
        parts, res = results[i]
        metrics = _metrics(engine, parts, res, peak, float(share) if len(by_scheme) > 1 else None)
        experimental = any(
            engine.inputs.crops[s.crop_id].agro_status != "approved" for o in scheme for s in o
        )
        flags = []
        if metrics.cash_gap.probability > P_GAP_LIMIT:
            flags.append("cash_gap_risk")
        if "income" in kinds and len(by_scheme) > 1 and share < 0.6:
            flags.append("depends_on_conditions")
        if experimental:
            flags.append("experimental")
        if res.unknown_inputs:
            flags.append("incomplete")
        if metrics.unsold:
            flags.append("no_buyer")
        if not engine.rotation_ok(scheme):
            flags.append("rotation_violation")
        financing = _financing_out(engine, res, kinds, selection.financed)
        if financing is not None:
            flags.append("needs_financing")
        summary_ru, summary_en = engine.describe(scheme, user_scheme)
        if i == 0:
            summary_ru, summary_en = "Текущий план без изменений", "Current plan, no changes"
        strategy_id, run_id = f"s_{generation_id}_{kinds[0]}", f"r_{generation_id}_{kinds[0]}"
        strategies.append(
            sch.StrategyOut(
                id=strategy_id, run_id=run_id, farm_id=farm_id, types=kinds,
                decisions=engine.decisions(scheme), summary_ru=summary_ru, summary_en=summary_en,
                metrics=metrics, flags=flags, financing=financing,
                agro_status="experimental" if experimental else "approved",
                completeness=res.completeness, unknown_inputs=list(res.unknown_inputs),
            )
        )
        stored = {"strategy_id": strategy_id, "scheme": [list(map(list, o)) for o in scheme]}
        for kind in kinds:  # одна схема доступна по id любой совпавшей стратегии
            runs[f"r_{generation_id}_{kind}"] = stored

    response = sch.GenerateResponse(
        generation_id=generation_id, farm_id=farm_id, farm_name=engine.inputs.name,
        scenario=req.scenario, schemes_checked=k, schemes_truncated=engine.truncated,
        peak_decades=[int(d) + 1 for d in peak], strategies=strategies,
        excluded=[
            sch.ExcludedStrategy(
                type=kind, constraint=why["constraint"], p_gap_limit=why["p_gap_limit"],
                best_p_gap=round(min(1.0, why["best_p_gap"]), 3),
                financing_needed_som=_int(why["financing_needed_som"]),
            )
            for kind, why in selection.excluded.items()
        ],
        provenance=engine.provenance(), result_hash="",
    )
    response.result_hash = result_hash(response.model_dump(mode="json", exclude={"result_hash"}))
    _save(
        {
            "generation_id": generation_id, "farm_id": farm_id, "seed": req.seed,
            "scenario": req.scenario.model_dump(mode="json"), "runs": runs,
            "response": response.model_dump(mode="json"),
        }
    )
    return response


def _financing_out(
    engine: Engine, res: PlanResult, kinds: list[str], financed: dict[str, float]
) -> sch.FinancingOut | None:
    """Финансирование для стратегии, выбранной сверх лимита риска (пример 15.3).

    Если схема совпала с несколькими целями, берётся самый строгий лимит (5% у «Пережить
    плохой год»): с этой суммой схема держит резерв для всех совпавших целей.
    """
    limits = {"income": P_GAP_LIMIT, "water_light": P_GAP_LIMIT, "resilient": P_GAP_RESILIENT}
    used = [limits[k] for k in kinds if k in financed]
    if not used:
        return None
    limit = min(used)
    need = financing_to_hold(res.cash, engine.inputs.econ.reserve_som, limit)
    if need.amount_som <= 0:
        return None
    return sch.FinancingOut(
        amount_som=_int(need.amount_som),
        month=None if need.month is None else need.month + 1,
        p_gap_limit=limit,
    )


def get_strategy(strategy_id: str) -> sch.StrategyOut:
    """GET /strategies/{id}."""
    record = _record_for("Strategy", strategy_id)
    run = record["runs"].get("r" + strategy_id[1:])
    for item in record["response"]["strategies"]:
        if run is not None and item["id"] == run["strategy_id"]:
            return sch.StrategyOut.model_validate(item)
    raise NotFoundError("Strategy", strategy_id)


def get_field_plan(strategy_ref: str, field_id: str, year: int) -> dict | None:
    """Культура и срок сева поля по стратегии — для ленты «Вода» (water.resolve_strategy_crop).

    Принимает id стратегии (s_…) или прогона (r_…). None — поля в стратегии нет.
    """
    if not strategy_ref or strategy_ref[0] not in "sr":
        return None
    record = _record_for("Strategy", strategy_ref)
    strategy_id = "s" + strategy_ref[1:]
    run = record["runs"].get("r" + strategy_ref[1:])
    item = next(
        (x for x in record["response"]["strategies"]
         if x["id"] == strategy_id or (run is not None and x["id"] == run["strategy_id"])),
        None,
    )
    if item is None:
        raise NotFoundError("Strategy", strategy_ref)
    decision = next((d for d in item["decisions"] if d["field_id"] == field_id), None)
    if decision is None:
        return None
    crop = _engine(record["farm_id"], record["seed"]).inputs.crops.get(decision["crop_id"])
    if crop is None:
        return None
    return {"crop": crop.raw or crop, "sowing_date": date(year, *crop.sowing_mmdd)}


# ----------------------------------------------------------------------------- М9: деньги


def get_cashflow(run_id: str) -> sch.CashflowResponse:
    """GET /runs/{id}/cashflow — остаток по месяцам с линией резерва и маркером разрыва."""
    record, run, engine, scheme = _run_context(run_id)
    _, res = engine.run(scheme, _scn(sch.ScenarioIn.model_validate(record["scenario"])))
    econ = engine.inputs.econ
    p10, p50, p90 = percentiles(res.cash)
    inflows = {"crop_revenue", "feed_sales", "milk"}
    months = [
        sch.CashflowMonth(
            month=m + 1,
            cash=sch.Percentiles(p10=_int(p10[m]), p50=_int(p50[m]), p90=_int(p90[m])),
            components={
                name: _int(flow[:, m].mean() * (1 if name in inflows else -1))
                for name, flow in res.flows.items()
            },
        )
        for m in range(12)
    ]
    return sch.CashflowResponse(
        run_id=run_id, strategy_id=run["strategy_id"],
        opening_cash_som=_int(econ.opening_cash_som), reserve_som=_int(econ.reserve_som),
        months=months, gap=engine.gap_out(res),
        receivable_som=_int(np.percentile(res.receivable, 50)),
        completeness=res.completeness, unknown_inputs=list(res.unknown_inputs),
        provenance=engine.provenance(),
    )


# ----------------------------------------------------------------------------- М12: стресс-тест


def _violates(engine: Engine, res: PlanResult) -> bool:
    return gap_probability(res.cash, engine.inputs.econ.reserve_som) > P_GAP_LIMIT + 1e-9


def stress(run_id: str, req: sch.StressRequest) -> sch.StressResponse:
    """POST /runs/{id}/stress — A, B, C и цена адаптации (М12)."""
    started = time.perf_counter()
    record, _, engine, scheme = _run_context(run_id)
    base = _scn(sch.ScenarioIn.model_validate(record["scenario"]))
    new = _scn(req)
    reserve = engine.inputs.econ.reserve_som

    parts_a, res_a = engine.run(scheme, base)
    parts_b, res_b = engine.run(scheme, new)
    out_a = engine.outcome(scheme, parts_a, res_a)
    out_b = engine.outcome(scheme, parts_b, res_b)
    fix_needed = _violates(engine, res_b)

    fixed, fixed_scheme, res_c = None, scheme, res_b
    if req.with_fix:
        for max_changes in (1, 2):  # минимум изменений; не более двух крупных в год (8.11)
            candidates = [
                c for c in neighbours(scheme, engine.options, max_changes)
                if c == scheme or engine.rotation_ok(c)
            ]
            runs = [engine.run(c, new) for c in candidates]
            best = pick_fix(
                [gap_probability(r.cash, reserve) for _, r in runs],
                [float(np.percentile(r.income, 50)) for _, r in runs],
                P_GAP_LIMIT,
            )
            if best != 0:
                fixed_scheme = candidates[best]
                parts_c, res_c = runs[best]
                fixed = engine.outcome(fixed_scheme, parts_c, res_c)
            if not _violates(engine, res_c):
                break

    if fixed is not None and not fix_needed:
        # план и так держится: менять его стоит только ради заметной прибавки (≥ 2%)
        gain = fixed.income_som.p50 - out_b.income_som.p50
        if gain < 0.02 * max(1, abs(out_b.income_som.p50)):
            fixed, fixed_scheme, res_c = None, scheme, res_b

    price = adaptation_price(
        out_a.income_som.p50, out_b.income_som.p50,
        fixed.income_som.p50 if fixed else out_b.income_som.p50,
        res_b.capex_som, res_c.capex_som, res_b.var_cost_som, res_c.var_cost_som,
    )
    if fixed is None:
        if fix_needed and req.with_fix:
            fix_ru = "Смена культур не спасает план: нужны деньги извне или меньше расходов"
            fix_en = "Changing crops does not save the plan: outside money or lower costs needed"
        elif req.with_fix:
            fix_ru, fix_en = "План выдерживает эти условия, менять ничего не нужно", (
                "The plan withstands these conditions, no changes needed"
            )
        else:
            fix_ru = fix_en = ""
    else:
        fix_ru, fix_en = engine.describe(fixed_scheme, scheme)
    losses = [loss for loss in out_b.field_losses if loss.yield_loss > 0.005]
    answers = sch.StressAnswers(
        water_decade=out_b.worst_decade,
        vulnerable_field=max(losses, key=lambda x: x.yield_loss) if losses else None,
        cash_gap=out_b.cash_gap,
        feed_extra_purchase_som=out_b.feed_purchase_som - out_a.feed_purchase_som,
        unsold=out_b.unsold,
        fix_summary_ru=fix_ru,
        fix_summary_en=fix_en,
    )
    # исправленный (или исходный, если смена культур не помогла) план всё ещё рвётся:
    # сколько денег привлечь и к какому месяцу, чтобы он держал резерв (пример 15.3)
    fixed_financing = None
    if fix_needed and req.with_fix and _violates(engine, res_c):
        need = financing_to_hold(res_c.cash, reserve, P_GAP_LIMIT)
        if need.amount_som > 0:
            fixed_financing = sch.FinancingOut(
                amount_som=_int(need.amount_som),
                month=None if need.month is None else need.month + 1,
                p_gap_limit=P_GAP_LIMIT,
            )
    return sch.StressResponse(
        run_id=run_id, scenario=sch.ScenarioIn.model_validate(req.model_dump()),
        baseline=out_a, stressed=out_b, fixed=fixed, fixed_financing=fixed_financing,
        fix_needed=fix_needed, fix_found=fixed is not None,
        damage_som=_int(price.damage_som), adaptation_gain_som=_int(price.gain_som),
        change_cost_som=_int(price.change_cost_som), answers=answers,
        elapsed_ms=_int((time.perf_counter() - started) * 1000),
        reserve_som=_int(reserve), provenance=engine.provenance(),
    )


# ----------------------------------------------------------------------------- М13: поломка

# (фактор, предел поиска, точность, единица, σ по умолчанию для запаса прочности — оценка)
_FACTORS: tuple[tuple[str, float, float, str, float], ...] = (
    ("water_supply_factor", 0.30, 0.005, "percent", 0.10),
    ("supply_shift_days", 40.0, 1.0, "days", 10.0),
    ("temp_delta_c", 5.0, 0.1, "celsius", 0.8),
    ("precip_factor", 0.20, 0.01, "percent", 0.25),
    ("feed_price_factor", 2.50, 0.01, "percent", 0.25),
    ("payment_delay_days", 180.0, 2.0, "days", 30.0),
    ("yield_factor", 0.40, 0.005, "percent", 0.15),
)


def _water_year_index(engine: Engine, scheme: Scheme, base: Scn) -> np.ndarray:
    """Водность года для плана: доля потребности брутто, закрытая подачей, к медиане лет.

    Год со значением 0,85 для хозяйства равносилен сокращению подачи на 15% в обычный год.
    Модельная оценка: дефицит нетто пересчитан в брутто через КПД поля 0,55.
    """
    parts = engine.parts(scheme, base)
    gross = sum(p.gross_m3.sum(axis=1) for p in parts)
    lack = sum(p.deficit_m3.sum(axis=1) for p in parts) / ASSUMED_FIELD_EFFICIENCY
    met = 1.0 - np.divide(lack, gross, out=np.zeros_like(gross), where=gross > 0)
    return met / np.median(met)


def get_breakpoints(run_id: str) -> sch.BreakpointsResponse:
    """GET /runs/{id}/breakpoints — минимальное отклонение, ломающее медианный исход (М13)."""
    record, _, engine, scheme = _run_context(run_id)
    if run_id in record.get("breakpoints", {}):
        return sch.BreakpointsResponse.model_validate(record["breakpoints"][run_id])

    base = _scn(sch.ScenarioIn.model_validate(record["scenario"]))
    reserve = engine.inputs.econ.reserve_som

    def broken(scn: Scn) -> dict | None:
        parts, res = engine.run(scheme, scn)
        gap = find_cash_gap(engine.median_cash(res), reserve)
        if not gap.feasible:
            return {"violated_constraint": "cash_gap", "month": gap.first_month + 1}
        losses = np.percentile(res.yield_loss, 50, axis=1)
        worst = int(losses.argmax())
        if losses[worst] > YIELD_LOSS_LIMIT:
            fld = engine.field(parts[worst].field_id)
            return {"violated_constraint": "yield_loss", "field_id": fld.id, "field_name": fld.name}
        return None

    def with_price(key: str):
        others = tuple(kv for kv in base.price_factors if kv[0] != key)
        return lambda v: Scn(**{**base.__dict__, "price_factors": (*others, (key, v))})

    base_violation = broken(base)
    if base_violation is not None:
        # план нарушает ограничение уже в базовых условиях — искать порог бессмысленно
        response = sch.BreakpointsResponse(
            run_id=run_id, breakpoints=[], holds=[], yield_loss_limit=YIELD_LOSS_LIMIT,
            base_violation=sch.BaseViolation(**base_violation), provenance=engine.provenance(),
        )
        record.setdefault("breakpoints", {})[run_id] = response.model_dump(mode="json")
        _save(record)
        return response

    factors = [
        (name, None, getattr(base, name), limit, tol, unit, sigma,
         lambda v, name=name: Scn(**{**base.__dict__, name: v}))
        for name, limit, tol, unit, sigma in _FACTORS
    ]
    sale_crops = sorted(
        {s.crop_id for o in scheme for s in o if not engine.params[s.crop_id].is_feed}
    )
    for key in (*sale_crops, "milk"):
        current = dict(base.price_factors).get(key, 1.0)
        factors.append(("price", key, current, 0.30, 0.005, "percent", 0.25, with_price(key)))

    water_index = _water_year_index(engine, scheme, base)
    year_values: dict[str, tuple[np.ndarray, bool]] = {
        "water_supply_factor": (water_index * base.water_supply_factor, True)
    }
    sigmas = {"water_supply_factor": float(water_index.std())}
    if engine.inputs.status.get("water") == "stub":
        anomalies = stub_year_anomalies(engine.inputs.years)
        year_values["temp_delta_c"] = (anomalies["temp"] + base.temp_delta_c, False)
        year_values["precip_factor"] = (anomalies["precip"] * base.precip_factor, True)
        sigmas["temp_delta_c"] = float(anomalies["temp"].std())
        sigmas["precip_factor"] = float(anomalies["precip"].std())

    found: list[sch.BreakpointOut] = []
    holds: list[str] = []
    for name, subject, start, limit, tol, unit, sigma, make in factors:
        threshold = bisect_threshold(lambda v, make=make: broken(make(v)) is not None,
                                     start, limit, tol)
        if threshold.value is None:
            holds.append(name if subject is None else f"{name}:{subject}")
            continue
        frequency = None
        if name in year_values and not threshold.already_broken:
            values, lower_is_worse = year_values[name]
            count, of = historical_frequency(values, threshold.value, lower_is_worse)
            frequency = sch.HistoricalFrequency(count=count, of=of)
        margin = safety_margin(start, threshold.value, sigmas.get(name) or sigma)
        delta = threshold.value - start
        crop = engine.inputs.crops.get(subject) if subject else None
        found.append(
            sch.BreakpointOut(
                factor=name, subject=subject,
                subject_name_ru=crop.name_ru if crop else ("Молоко" if subject else None),
                subject_name_en=crop.name_en if crop else ("Milk" if subject else None),
                unit=unit, base_value=round(start, 3), threshold_value=round(threshold.value, 3),
                delta=round(delta * 100 if unit == "percent" else delta, 1),
                already_broken=threshold.already_broken, historical_frequency=frequency,
                safety_margin_sigma=None if margin is None else round(margin, 2),
                **broken(make(threshold.value)),
            )
        )
    found.sort(
        key=lambda b: (not b.already_broken, b.safety_margin_sigma is None,
                       b.safety_margin_sigma or 0.0, b.factor, b.subject or "")
    )
    response = sch.BreakpointsResponse(
        run_id=run_id, breakpoints=found, holds=holds, yield_loss_limit=YIELD_LOSS_LIMIT,
        provenance=engine.provenance(),
    )
    record.setdefault("breakpoints", {})[run_id] = response.model_dump(mode="json")
    _save(record)
    return response


# ----------------------------------------------------------------------------- контракт для ИИ


def get_run_summary(run_id: str) -> sch.RunSummary:
    """Сводка прогона для ИИ-помощника. Точки поломки — только если уже посчитаны."""
    record, run, engine, _ = _run_context(run_id)
    strategy = get_strategy(run["strategy_id"])
    cached = record.get("breakpoints", {}).get(run_id)
    return sch.RunSummary(
        run_id=run_id, strategy_id=strategy.id, farm_id=strategy.farm_id, types=strategy.types,
        summary_ru=strategy.summary_ru, summary_en=strategy.summary_en,
        decisions=strategy.decisions, metrics=strategy.metrics, flags=strategy.flags,
        breakpoints=(
            sch.BreakpointsResponse.model_validate(cached).breakpoints if cached else None
        ),
        provenance=engine.provenance(),
    )
