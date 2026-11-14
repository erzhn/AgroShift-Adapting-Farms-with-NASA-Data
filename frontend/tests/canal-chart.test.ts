import assert from "node:assert/strict";
import test from "node:test";
import { buildCanalChartData } from "../src/lib/canal-chart.ts";

test("canal chart produces all 36 decades and keeps API demand series", () => {
  const result = buildCanalChartData(
    [
      {
        decade: 2,
        supply_head_m3: 170,
        demand_head_before_m3: 220,
        demand_head_after_m3: 180,
      },
    ],
    [],
  );

  assert.equal(result.length, 36);
  assert.deepEqual(result[1], {
    decade: 2,
    supply_head_m3: 170,
    demand_head_before_m3: 220,
    demand_head_after_m3: 180,
  });
});

test("canal chart falls back to the saved supply schedule for missing demand supply", () => {
  const result = buildCanalChartData(
    [{ decade: 7, demand_head_before_m3: 90, demand_head_after_m3: 80 }],
    [{ decade: 7, volume_m3: 65 }],
  );

  assert.equal(result[6].supply_head_m3, 65);
  assert.equal(result[6].demand_head_before_m3, 90);
  assert.equal(result[6].demand_head_after_m3, 80);
  assert.equal(result[5].supply_head_m3, null);
});
