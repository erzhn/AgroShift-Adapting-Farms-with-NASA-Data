"use client";
import MoneyLane from "../strategies/MoneyLane";
import type { LaneProps } from "./PlanningLanes";

export default function MoneyIntegration({ runId, month, onMonthChange, language }: LaneProps) {
  return runId ? (
    <MoneyLane
      key={runId}
      runId={runId}
      month={month}
      onMonthChange={onMonthChange}
      height={190}
      language={language}
    />
  ) : null;
}
