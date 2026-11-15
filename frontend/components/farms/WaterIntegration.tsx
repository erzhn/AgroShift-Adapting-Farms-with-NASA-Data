"use client";
import WaterLane from "../water/WaterLane";
import type { LaneProps } from "./PlanningLanes";

/** Adapter: main-screen LaneProps -> WaterLane (water module, M4–M6). */
export default function WaterIntegration({
  farm,
  strategyId,
  runId,
  scenario,
  month,
  onMonthChange,
  language,
}: LaneProps) {
  const fieldIds = farm.fields.map((f) => f.id);
  if (fieldIds.length === 0) return null;
  // "current" = the farmer's own plan; any other choice -> the strategy run
  const strategy = strategyId === "current" ? undefined : runId;
  return (
    <WaterLane
      fieldIds={fieldIds}
      strategy={strategy}
      scenario={scenario?.preset_code}
      selectedDecade={(month - 1) * 3 + 2}
      onSelectDecade={(decade) => onMonthChange?.(Math.ceil(decade / 3))}
      lang={language}
      height={190}
    />
  );
}
