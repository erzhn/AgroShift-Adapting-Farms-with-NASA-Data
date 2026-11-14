import type { Crop, Field, Scenario as Preset } from "./api/farms.ts";
import type { Scenario, Strategy } from "./api/strategies.ts";

/** Historical presets need actual climate snapshots; never approximate 2023 with a multiplier. */
export function scenarioForStrategy(preset: Preset | null): Partial<Scenario> | null {
  if (!preset) return {};
  if (preset.climate_params.year !== null) return null;
  const { feed, ...prices } = preset.price_factors;
  return {
    water_supply_factor: preset.water_supply_factor,
    water_months: preset.water_supply_months || [],
    supply_shift_days: preset.supply_shift_days,
    temp_delta_c: preset.temp_delta_c,
    precip_factor: preset.precip_factor,
    yield_factor: preset.yield_factor,
    price_factors: prices,
    feed_price_factor: feed ?? 1,
    payment_delay_days: preset.payment_delay_days,
  };
}

/** Preview decisions without mutating saved seasons or inventing sowing dates. */
export function previewFields(
  fields: Field[],
  crops: Crop[],
  strategy: Strategy | undefined,
  year: number,
): Field[] {
  if (!strategy || strategy.types.includes("user")) return fields;
  return fields.map((field) => {
    const decision = strategy.decisions.find((d) => d.field_id === field.id);
    if (!decision || decision.action === "keep") return field;
    return {
      ...field,
      seasons: field.seasons.map((season) =>
        season.year === year && season.is_main
          ? {
              ...season,
              crop_id: decision.crop_id,
              crop_variant_id: crops.find((c) => c.id === decision.crop_id)?.variants[0]?.id || "",
              sowing_date: null,
              harvest_date: null,
              planned_yield_t_ha: null,
            }
          : season,
      ),
    };
  });
}
