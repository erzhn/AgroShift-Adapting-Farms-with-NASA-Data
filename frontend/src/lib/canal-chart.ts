export type CanalDemandDecade = {
  decade: number;
  supply_head_m3?: number | null;
  demand_head_before_m3?: number | null;
  demand_head_after_m3?: number | null;
};

export type CanalSupplyDecade = {
  decade: number;
  volume_m3: number | null;
};

export type CanalChartPoint = {
  decade: number;
  supply_head_m3: number | null;
  demand_head_before_m3: number;
  demand_head_after_m3: number;
};

export function buildCanalChartData(
  demand: readonly CanalDemandDecade[],
  supply: readonly CanalSupplyDecade[],
): CanalChartPoint[] {
  const demandByDecade = new Map(demand.map((row) => [row.decade, row]));
  const supplyByDecade = new Map(supply.map((row) => [row.decade, row]));

  return Array.from({ length: 36 }, (_, index) => {
    const decade = index + 1;
    const calculated = demandByDecade.get(decade);
    return {
      decade,
      supply_head_m3:
        calculated?.supply_head_m3 ?? supplyByDecade.get(decade)?.volume_m3 ?? null,
      demand_head_before_m3: calculated?.demand_head_before_m3 ?? 0,
      demand_head_after_m3: calculated?.demand_head_after_m3 ?? 0,
    };
  });
}
