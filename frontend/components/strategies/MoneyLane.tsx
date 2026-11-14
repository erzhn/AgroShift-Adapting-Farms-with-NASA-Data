"use client";

// Лента «Деньги» для главного экрана и экрана стратегий: остаток по месяцам, линия резерва
// семьи, маркер кассового разрыва.
//
// Вставка на главный экран (Баяман):
//   <MoneyLane farmId={farm.id} month={month} onMonthChange={setMonth} />
// Без runId лента сама берёт прогон из localStorage["agroshift.runId"] (стратегия, выбранная
// на экране «Варианты будущего»), а если его нет — строит варианты и показывает «Мой вариант».

import type { EChartsOption } from "echarts";
import { useEffect, useMemo, useState } from "react";

import {
  type CashflowResponse,
  type StrategyType,
  STORAGE_KEYS,
  generateStrategies,
  getCashflow,
} from "../../lib/api/strategies";
import EChart from "./EChart";
import { money, useLang } from "./i18n";
import css from "./strategies.module.css";

interface Props {
  runId?: string;
  farmId?: string;
  strategyType?: StrategyType;
  /** выбранный на шкале месяц, 1–12 */
  month?: number;
  onMonthChange?: (month: number) => void;
  height?: number;
  /** узкая лента без заголовка и легенды — для главного экрана */
  compact?: boolean;
}

const INK = "#1c2b24";
const GREEN = "#1f6f4a";
const RED = "#c0392b";

async function resolveRun(
  runId: string | undefined,
  farmId: string | undefined,
  type: StrategyType,
  signal: AbortSignal,
): Promise<string | null> {
  if (runId) return runId;
  let stored: string | null = null;
  try {
    stored = window.localStorage.getItem(STORAGE_KEYS.runId);
  } catch {
    // нет доступа к хранилищу — строим заново
  }
  if (stored) return stored;
  if (!farmId) return null;
  const generated = await generateStrategies(farmId, {}, signal);
  const strategy =
    generated.strategies.find((s) => s.types.includes(type)) ?? generated.strategies[0];
  return strategy?.run_id ?? null;
}

export default function MoneyLane({
  runId,
  farmId,
  strategyType = "user",
  month,
  onMonthChange,
  height,
  compact = false,
}: Props) {
  const [lang, t] = useLang();
  const [data, setData] = useState<CashflowResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        setError(null);
        let id = await resolveRun(runId, farmId, strategyType, controller.signal);
        if (!id) return;
        let cashflow: CashflowResponse;
        try {
          cashflow = await getCashflow(id, controller.signal);
        } catch (first) {
          // сохранённый прогон устарел (хозяйство изменилось) — строим заново
          if (runId || !farmId || controller.signal.aborted) throw first;
          try {
            window.localStorage.removeItem(STORAGE_KEYS.runId);
          } catch {
            // хранилище недоступно
          }
          id = await resolveRun(undefined, farmId, strategyType, controller.signal);
          if (!id) throw first;
          cashflow = await getCashflow(id, controller.signal);
        }
        setData(cashflow);
      } catch (e) {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e));
      }
    };
    load();
    const onSelect = () => !runId && load();
    window.addEventListener("agroshift:run", onSelect);
    return () => {
      controller.abort();
      window.removeEventListener("agroshift:run", onSelect);
    };
  }, [runId, farmId, strategyType]);

  const option = useMemo<EChartsOption | null>(() => {
    if (!data) return null;
    const p10 = data.months.map((m) => m.cash.p10);
    const p50 = data.months.map((m) => m.cash.p50);
    const p90 = data.months.map((m) => m.cash.p90);
    const gap = data.gap.first_month;
    return {
      animationDuration: 300,
      grid: { left: 8, right: 16, top: compact ? 12 : 28, bottom: 4, containLabel: true },
      tooltip: {
        trigger: "axis",
        formatter: (params) => {
          const i = (Array.isArray(params) ? params[0] : params).dataIndex ?? 0;
          return [
            `<b>${t.monthsFull[i]}</b>`,
            `${t.median}: ${money(p50[i], t, lang)}`,
            `${t.band}: ${money(p10[i], t, lang)} … ${money(p90[i], t, lang)}`,
            `${t.reserve}: ${money(data.reserve_som, t, lang)}`,
          ].join("<br/>");
        },
      },
      xAxis: {
        type: "category",
        data: t.months,
        boundaryGap: false,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "#c9d2cc" } },
        axisLabel: { color: "#5b6a62" },
      },
      yAxis: {
        type: "value",
        splitLine: { lineStyle: { color: "#e6ebe7" } },
        axisLabel: {
          color: "#5b6a62",
          formatter: (v: number) => `${Math.round(v / 1000)}`,
        },
        name: compact ? undefined : `${t.thousand} ${t.som}`,
        nameTextStyle: { color: "#5b6a62", align: "left" },
      },
      series: [
        {
          name: "p10",
          type: "line",
          data: p10,
          stack: "band",
          stackStrategy: "all",
          symbol: "none",
          lineStyle: { opacity: 0 },
          silent: true,
        },
        {
          name: t.band,
          type: "line",
          data: p90.map((v, i) => v - p10[i]),
          stack: "band",
          stackStrategy: "all",
          symbol: "none",
          lineStyle: { opacity: 0 },
          areaStyle: { color: GREEN, opacity: 0.14 },
          silent: true,
        },
        {
          name: t.median,
          type: "line",
          data: p50,
          symbol: "circle",
          symbolSize: 6,
          lineStyle: { color: GREEN, width: 2.5 },
          itemStyle: { color: GREEN },
          markLine: {
            silent: true,
            symbol: "none",
            data: [
              {
                yAxis: data.reserve_som,
                lineStyle: { color: RED, type: "dashed", width: 1.5 },
                label: {
                  formatter: t.reserve,
                  position: "insideStartTop",
                  color: RED,
                  fontSize: 11,
                },
              },
              ...(month
                ? [
                    {
                      xAxis: month - 1,
                      lineStyle: { color: INK, type: "solid" as const, width: 1 },
                      label: { show: false },
                    },
                  ]
                : []),
            ],
          },
          markPoint:
            gap === null
              ? undefined
              : {
                  symbol: "circle",
                  symbolSize: 14,
                  itemStyle: { color: RED, borderColor: "#fff", borderWidth: 2 },
                  label: {
                    formatter: t.gapMark,
                    position: "bottom",
                    color: RED,
                    fontWeight: 600,
                    fontSize: 11,
                  },
                  data: [{ name: t.gapMark, coord: [gap - 1, p50[gap - 1]] }],
                },
        },
      ],
    };
  }, [data, month, compact, t, lang]);

  if (error) return <p className={css.error}>{t.error}: {error}</p>;
  if (!option || !data) return <p className={css.muted}>{t.loading}</p>;

  const gap = data.gap;
  return (
    <div className={css.root}>
      {!compact && (
        <p className={gap.first_month ? css.verdictBad : css.verdictOk}>
          {gap.first_month
            ? `${t.gapIn(t.monthsFull[gap.first_month - 1])} — ${t.needMoney(
                money(gap.financing_needed_som, t, lang),
              )}`
            : t.noGap}
        </p>
      )}
      <EChart
        option={option}
        height={height ?? (compact ? 120 : 280)}
        onClickIndex={(i) => i >= 0 && i < 12 && onMonthChange?.(i + 1)}
        ariaLabel={t.money}
      />
      {!compact && <p className={css.hint}>{t.moneyHint}</p>}
    </div>
  );
}
