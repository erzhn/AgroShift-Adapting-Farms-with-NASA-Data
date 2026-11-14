"use client";
import { useEffect, useState } from "react";
import type { Farm, Scenario } from "@/lib/api/farms";
import { generateStrategies, type GenerateResponse } from "@/lib/api/strategies";
import { planYear, seasonFor } from "@/lib/farms";
import { scenarioForStrategy } from "@/lib/planning";

export default function useFarmStrategies(
  farm: Farm | undefined,
  year: number,
  preset: Scenario | null,
) {
  const conditions = scenarioForStrategy(preset);
  const eligible =
    !!farm &&
    year === planYear(farm.fields) &&
    farm.fields.length > 0 &&
    farm.fields.every((f) => seasonFor(f, year)) &&
    farm.cash_som !== null &&
    farm.family_reserve_som !== null;
  const key = eligible && conditions !== null ? JSON.stringify([farm, conditions]) : "";
  const [result, setResult] = useState<{ key: string; data?: GenerateResponse; error?: string }>({
    key: "",
  });
  useEffect(() => {
    if (!key) return;
    const controller = new AbortController();
    const [snapshot, scenario] = JSON.parse(key) as [Farm, NonNullable<typeof conditions>];
    generateStrategies(snapshot.id, { scenario }, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setResult({ key, data });
      })
      .catch((error) => {
        if (!controller.signal.aborted) setResult({ key, error: (error as Error).message });
      });
    return () => controller.abort();
  }, [key]);
  return {
    data: key && result.key === key ? result.data : undefined,
    error: key && result.key === key ? result.error : undefined,
    loading: !!key && result.key !== key,
    historical: conditions === null,
    eligible,
  };
}
