import assert from "node:assert/strict";
import test from "node:test";
import { optionalNumber, seasonFor, stageFor } from "../lib/farms.ts";
import { scenarioForStrategy, previewFields } from "../lib/planning.ts";
import type { Field, Scenario, Season } from "../lib/api/farms.ts";
import type { Strategy } from "../lib/api/strategies.ts";

const season: Season = {
  id: "s",
  crop_id: "maize",
  crop_variant_id: "silage",
  year: 2027,
  is_main: true,
  sowing_date: "2027-04-25",
  harvest_date: "2027-08-22",
  planned_yield_t_ha: 30,
};
const field = { id: "f", seasons: [season] } as Field;
const preset: Scenario = {
  id: "p",
  preset_code: "water_minus_20",
  name: "Water",
  water_supply_factor: 0.8,
  water_supply_months: [7, 8],
  supply_shift_days: 0,
  price_factors: {},
  payment_delay_days: 0,
  temp_delta_c: 0,
  precip_factor: 1,
  yield_factor: 1,
  climate_params: { year: null, percentile: 50 },
};

test("empty, zero, decimal and integer input are distinct", () => {
  assert.equal(optionalNumber(" "), null);
  assert.equal(optionalNumber("0", true), 0);
  assert.equal(optionalNumber("1,25"), 1.25);
  assert.equal(optionalNumber("-150", true), -150);
  for (const value of ["NaN", "Infinity", "9007199254740992", "abc", "1.5"]) {
    assert.throws(() => optionalNumber(value, true));
  }
});
test("timeline respects actual dates, unknown years and winter sowing", () => {
  assert.equal(stageFor(season, 4, 2027), "sowing");
  assert.equal(stageFor(season, 7, 2027), "growing");
  assert.equal(stageFor(season, 8, 2027), "harvest");
  assert.equal(stageFor(season, 12, 2027), "rest");
  assert.equal(seasonFor(field, 2028), undefined);
  assert.equal(stageFor(undefined, 7, 2028), "unknown");
  assert.equal(stageFor({ ...season, sowing_date: "2026-10-01" }, 1, 2027), "growing");
});
test("a partial crop calendar never fabricates a growing phase", () => {
  assert.equal(stageFor({ ...season, harvest_date: null }, 7, 2027), "unknown");
});
test("water stress keeps July/August scope and feed stress is feed-only", () => {
  const water = scenarioForStrategy(preset)!;
  assert.deepEqual(water.water_months, [7, 8]);
  assert.equal(water.water_supply_factor, 0.8);
  const feed = scenarioForStrategy({
    ...preset,
    price_factors: { feed: 1.4 },
    water_supply_months: null,
  })!;
  assert.equal(feed.feed_price_factor, 1.4);
  assert.deepEqual(feed.price_factors, {});
  assert.deepEqual(feed.water_months, []);
});
test("historical conditions cannot silently become an estimated year", () => {
  assert.equal(
    scenarioForStrategy({ ...preset, climate_params: { year: 2023, percentile: null } }),
    null,
  );
  assert.deepEqual(scenarioForStrategy(null), {});
});
test("strategy preview leaves the original crop and dates intact", () => {
  const strategy = {
    types: ["income"],
    decisions: [{ field_id: "f", crop_id: "wheat", action: "switch" }],
  } as Strategy;
  const preview = previewFields([field], [], strategy, 2027);
  assert.equal(preview[0].seasons[0].crop_id, "wheat");
  assert.equal(preview[0].seasons[0].sowing_date, null);
  assert.equal(field.seasons[0].crop_id, "maize");
  assert.equal(field.seasons[0].sowing_date, "2027-04-25");
});
