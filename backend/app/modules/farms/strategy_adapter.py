"""Explicit bridge from the shared farm contracts to the strategy module.

Missing water/feed/economic models remain labelled estimates. IDs, crop products,
season inputs, monthly costs, prices and user edits come from the database.
"""

from dataclasses import replace

from agroshift_core.plan_eval import CropParams
from app.modules.farms.schemas import Crop, Farm


def strategy_inputs(farm: Farm, catalog: list[Crop]):
    # Local import avoids a cycle: the strategy service discovers this adapter at runtime.
    from app.services.strategy_inputs import (
        DEMO_CROPS,
        DEMO_GRAZING,
        DEMO_HERD,
        STUB_YEARS,
        CropInfo,
        FarmInputs,
        FieldInfo,
        demo_econ,
        herd_demand_dm_kg,
    )

    seasons = [s for f in farm.fields for s in f.seasons if s.is_main]
    if not seasons:
        raise ValueError("Сначала задайте культуры для полей")
    year = max(s.year for s in seasons)
    current = {
        f.id: next((s for s in f.seasons if s.is_main and s.year == year), None)
        for f in farm.fields
    }
    if any(s is None for s in current.values()):
        raise ValueError("Укажите культуру на каждом поле в последнем сезоне")
    if farm.cash_som is None or farm.family_reserve_som is None:
        raise ValueError("Укажите свободные средства и месячные расходы семьи")

    crops = {}
    for crop in catalog:
        if not crop.variants:
            continue
        base = DEMO_CROPS.get("corn" if crop.code == "maize" else crop.code)
        if base is None:
            continue  # No agronomic rules for this crop in the current strategy engine.
        active = [s for s in current.values() if s.crop_id == crop.id]
        variant_ids = {s.crop_variant_id for s in active}
        if len(variant_ids) > 1:
            raise ValueError("Расчёт пока поддерживает один вариант каждой культуры")
        variant = next((v for v in crop.variants if v.id in variant_ids), crop.variants[0])
        costs = [0.0] * 12
        for cost in variant.costs:
            costs[cost.month - 1] += cost.cost_som_ha
        harvest = list(base.params.harvest_shares)
        end_dates = {s.harvest_date for s in active if s.harvest_date}
        if len(end_dates) == 1 and variant.product != "hay":
            harvest = [0.0] * 12
            harvest[next(iter(end_dates)).month - 1] = 1.0
        sowing = next((s.sowing_date for s in active if s.sowing_date), None)
        crops[str(crop.id)] = CropInfo(
            params=CropParams(
                crop_id=str(crop.id),
                yield_t_ha=variant.yield_potential_t_ha,
                price_som_t=crop.price.price_som if crop.price else None,
                cost_som_ha_by_month=tuple(costs),
                harvest_shares=tuple(harvest),
                is_feed=variant.product in {"hay", "silage"},
                dm_share=0.35 if variant.product == "silage" else base.params.dm_share,
                max_volume_t=base.params.max_volume_t,
                establish_yield_factor=base.params.establish_yield_factor,
            ),
            name_ru=crop.name_ru,
            name_en=crop.name_en,
            perennial=crop.is_perennial,
            repeat_allowed=base.repeat_allowed,
            plantable=base.plantable,
            uproot_cost_som_ha=base.uproot_cost_som_ha,
            sowing_mmdd=(sowing.month, sowing.day) if sowing else base.sowing_mmdd,
            agro_status="experimental",
            kc=(crop.kc_ini, crop.kc_mid, crop.kc_end),
            stage_days=tuple(variant.stage_days_override or crop.stage_days),
            ky=crop.ky,
            raw=crop,
        )
    fields = tuple(
        FieldInfo(str(f.id), f.name, f.area_ha, str(current[f.id].crop_id), f) for f in farm.fields
    )
    if any(f.crop_id not in crops for f in fields):
        raise ValueError("Для выбранной культуры ещё нет правил расчёта стратегии")
    demo = demo_econ()
    count = sum(h.head_count for h in farm.herds if h.species == "cow" and h.purpose == "milk")
    scale = count / DEMO_HERD["head_count"]
    demand = herd_demand_dm_kg(count, DEMO_HERD["dmi_kg_day"], DEMO_GRAZING)
    econ = replace(
        demo,
        opening_cash_som=farm.cash_som,
        reserve_som=farm.family_reserve_som,
        family_by_month=(float(farm.family_reserve_som),) * 12,
        milk_income_by_month=tuple(v * scale for v in demo.milk_income_by_month),
        herd_cost_by_month=tuple(v * scale for v in demo.herd_cost_by_month),
        feed_demand_dm_kg=tuple(float(v) for v in demand),
        feed_opening_stock_dm_kg=float(demand[:5].sum()),
    )
    return FarmInputs(
        farm_id=str(farm.id),
        name=farm.name,
        fields=fields,
        crops=crops,
        econ=econ,
        years=STUB_YEARS,
        status={"farm": "service", "water": "stub"},
        warnings=(
            "Вода и климат — демонстрационная модель, не наблюдения NASA",
            "Кормление, доля сухого вещества, молоко, запас корма, отсрочка и выкорчёвка — оценки",
            "Севообороты требуют проверки агронома; используется последний сезон хозяйства",
        ),
    )
