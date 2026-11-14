"use client";

// Стресс-тест (FR-5.1–5.3): ползунки UC-3, готовые сценарии, пять ответов, две колонки
// «исходный план / исправленный» и цена адаптации.

import type { EChartsOption } from "echarts";
import { useEffect, useMemo, useState } from "react";

import {
  BASE_SCENARIO,
  type PlanOutcome,
  type Scenario,
  type StressResponse,
  stressRun,
} from "../../lib/api/strategies";
import EChart from "./EChart";
import { type Dict, type Lang, decadeLabel, money, percent, volume } from "./i18n";
import css from "./strategies.module.css";

interface Props {
  runId: string;
  t: Dict;
  lang: Lang;
}

type Key = keyof Dict["slider"];

interface Slider {
  key: Key;
  field: keyof Scenario;
  min: number;
  max: number;
  step: number;
  kind: "percent" | "days" | "celsius";
}

// диапазоны — UC-3 ТЗ
const SLIDERS: Slider[] = [
  { key: "water", field: "water_supply_factor", min: 0.5, max: 1.2, step: 0.01, kind: "percent" },
  { key: "shift", field: "supply_shift_days", min: -30, max: 30, step: 1, kind: "days" },
  { key: "temp", field: "temp_delta_c", min: 0, max: 3, step: 0.1, kind: "celsius" },
  { key: "precip", field: "precip_factor", min: 0.5, max: 1.3, step: 0.01, kind: "percent" },
  { key: "price", field: "price_factor", min: 0.5, max: 1.5, step: 0.01, kind: "percent" },
  { key: "feed", field: "feed_price_factor", min: 0.5, max: 1.5, step: 0.01, kind: "percent" },
  { key: "delay", field: "payment_delay_days", min: 0, max: 120, step: 5, kind: "days" },
  { key: "yield", field: "yield_factor", min: 0.7, max: 1.3, step: 0.01, kind: "percent" },
];

// готовые сценарии FR-5.2
const PRESETS: { key: keyof Dict["preset"]; patch: Partial<Scenario> }[] = [
  { key: "hot2023", patch: { temp_delta_c: 2, precip_factor: 0.8 } },
  { key: "lowSnow", patch: { water_supply_factor: 0.75 } },
  { key: "waterJulAug", patch: { water_supply_factor: 0.8, water_months: [7, 8] } },
  { key: "feed40", patch: { feed_price_factor: 1.4 } },
  { key: "delay60", patch: { payment_delay_days: 60 } },
];

function signed(value: number, digits = 0): string {
  const text = Math.abs(value).toFixed(digits);
  if (Number(text) === 0) return "0";
  return `${value > 0 ? "+" : "−"}${text}`;
}

function sliderValue(s: Slider, value: number, t: Dict): string {
  if (s.kind === "percent") return `${signed((value - 1) * 100)}%`;
  if (s.kind === "celsius") return `${signed(value, 1)} °C`;
  return `${signed(value)} ${t.days}`;
}

function Outcome({
  title,
  outcome,
  reserve,
  t,
  lang,
}: {
  title: string;
  outcome: PlanOutcome;
  reserve: number;
  t: Dict;
  lang: Lang;
}) {
  const gap = outcome.cash_gap;
  const lowest = Math.min(...outcome.cash_p50);
  return (
    <div className={gap.first_month ? css.outcomeBad : css.outcomeOk}>
      <h4>{title}</h4>
      <p className={css.outcomeVerdict}>
        {gap.first_month
          ? `${t.gapIn(t.monthsFull[gap.first_month - 1])}, ${t.needMoney(
              money(gap.financing_needed_som, t, lang),
            )}`
          : t.noGap}
      </p>
      <dl>
        <dt>{t.incomeYear}</dt>
        <dd>{money(outcome.income_som.p50, t, lang)}</dd>
        <dt>{t.range}</dt>
        <dd>
          {money(outcome.income_som.p10, t, lang)} — {money(outcome.income_som.p90, t, lang)}
        </dd>
        <dt>min · {t.reserve.toLowerCase()}</dt>
        <dd>
          {money(lowest, t, lang)} · {money(reserve, t, lang)}
        </dd>
        <dt>{t.gapChance("")}</dt>
        <dd>{percent(gap.probability)}</dd>
      </dl>
      <ul className={css.decisions}>
        {outcome.decisions.map((d) => (
          <li key={`${d.field_id}-${d.crop_id}`} className={d.action === "keep" ? undefined : css.changed}>
            {d.field_name}: {(lang === "ru" ? d.crop_name_ru : d.crop_name_en).toLowerCase()},{" "}
            {d.area_ha} {lang === "ru" ? "га" : "ha"}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function StressPanel({ runId, t, lang }: Props) {
  const [scenario, setScenario] = useState<Scenario>(BASE_SCENARIO);
  const [preset, setPreset] = useState<string | null>(null);
  const [result, setResult] = useState<StressResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setBusy(true);
      try {
        setResult(await stressRun(runId, scenario, controller.signal));
        setError(null);
      } catch (e) {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    }, 180); // ждём, пока ползунок остановится
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [runId, scenario]);

  const chart = useMemo<EChartsOption | null>(() => {
    if (!result) return null;
    const line = (name: string, data: number[], color: string, dashed = false) => ({
      name,
      type: "line" as const,
      data,
      symbol: "none",
      lineStyle: { color, width: dashed ? 1.5 : 2.5, type: dashed ? ("dashed" as const) : ("solid" as const) },
      itemStyle: { color },
    });
    const series = [
      line(t.baseLine, result.baseline.cash_p50, "#8a968f", true),
      line(t.original, result.stressed.cash_p50, "#c0392b"),
    ];
    if (result.fixed) series.push(line(t.fixed, result.fixed.cash_p50, "#1f6f4a"));
    return {
      animationDuration: 200,
      grid: { left: 8, right: 16, top: 36, bottom: 4, containLabel: true },
      legend: { top: 0, left: 0, icon: "roundRect", itemWidth: 14, itemHeight: 3, textStyle: { color: "#1c2b24" } },
      tooltip: {
        trigger: "axis",
        valueFormatter: (v) => money(Number(v), t, lang),
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
        axisLabel: { color: "#5b6a62", formatter: (v: number) => `${Math.round(v / 1000)}` },
      },
      series: [
        ...series,
        {
          name: t.reserve,
          type: "line",
          data: t.months.map(() => result.reserve_som),
          symbol: "none",
          lineStyle: { color: "#1c2b24", width: 1, type: "dotted" },
          itemStyle: { color: "#1c2b24" },
        },
      ],
    };
  }, [result, t, lang]);

  const set = (field: keyof Scenario, value: number) => {
    setPreset(null);
    // ползунок воды относится ко всему сезону, а не к месяцам готового сценария
    setScenario((s) => ({ ...s, [field]: value, ...(field === "water_supply_factor" ? { water_months: [] } : {}) }));
  };

  const a = result?.answers;
  return (
    <div className={css.stress}>
      <div className={css.controls}>
        <p className={css.controlsTitle}>{t.presets}</p>
        <div className={css.presets}>
          {PRESETS.map((p) => (
            <button
              key={p.key}
              type="button"
              className={preset === p.key ? css.presetOn : css.preset}
              aria-pressed={preset === p.key}
              onClick={() => {
                setPreset(p.key);
                setScenario({ ...BASE_SCENARIO, ...p.patch });
              }}
            >
              {t.preset[p.key]}
            </button>
          ))}
        </div>
        {SLIDERS.map((s) => {
          const value = scenario[s.field] as number;
          const base = BASE_SCENARIO[s.field] as number;
          return (
            <label key={s.key} className={css.slider}>
              <span>{t.slider[s.key]}</span>
              <output className={value === base ? css.sliderBase : css.sliderMoved}>
                {sliderValue(s, value, t)}
              </output>
              <input
                type="range"
                min={s.min}
                max={s.max}
                step={s.step}
                value={value}
                onChange={(e) => set(s.field, Number(e.target.value))}
              />
            </label>
          );
        })}
        <button
          type="button"
          className={css.reset}
          onClick={() => {
            setPreset(null);
            setScenario(BASE_SCENARIO);
          }}
        >
          {t.reset}
        </button>
      </div>

      <div className={css.results} aria-busy={busy}>
        {error && <p className={css.error}>{t.error}: {error}</p>}
        {!result && !error && <p className={css.muted}>{t.loading}</p>}
        {result && a && (
          <>
            <ol className={css.answers}>
              <li>
                <span>{t.q.water}</span>
                <strong>
                  {a.water_decade
                    ? `${decadeLabel(a.water_decade.decade, t)} — ${t.deficitOf(
                        volume(a.water_decade.deficit_m3, lang),
                      )}`
                    : t.noWaterDeficit}
                </strong>
              </li>
              <li>
                <span>{t.q.field}</span>
                <strong>
                  {a.vulnerable_field
                    ? `${a.vulnerable_field.field_name} — ${t.lossOf(
                        percent(a.vulnerable_field.yield_loss),
                      )}`
                    : t.noLoss}
                </strong>
              </li>
              <li className={a.cash_gap.first_month ? css.answerBad : undefined}>
                <span>{t.q.cash}</span>
                <strong>
                  {a.cash_gap.first_month
                    ? `${t.monthsFull[a.cash_gap.first_month - 1]} — ${t.needMoney(
                        money(a.cash_gap.financing_needed_som, t, lang),
                      )}`
                    : t.noGap}
                </strong>
              </li>
              <li>
                <span>{t.q.feed}</span>
                <strong>
                  {[
                    Math.abs(a.feed_extra_purchase_som) >= 1000
                      ? t.feedExtra(money(a.feed_extra_purchase_som, t, lang))
                      : t.feedSame,
                    ...a.unsold.map((u) => t.unsoldT(String(u.tonnes))),
                  ].join("; ")}
                </strong>
              </li>
              <li className={result.fix_found ? css.answerGood : undefined}>
                <span>{t.q.fix}</span>
                <strong>
                  {lang === "ru" ? a.fix_summary_ru : a.fix_summary_en}
                  {result.fix_found &&
                    ` — ${t.changeCost.toLowerCase()}: ${
                      result.change_cost_som < 0
                        ? `${money(-result.change_cost_som, t, lang)} ${t.cheaper}`
                        : money(result.change_cost_som, t, lang)
                    }`}
                </strong>
              </li>
            </ol>

            {chart && (
              <div className={css.panel}>
                <p className={css.hint}>
                  {t.money}, {t.thousand} {t.som}
                </p>
                <EChart option={chart} height={240} ariaLabel={t.money} />
              </div>
            )}

            <div className={css.columns}>
              <Outcome
                title={`${t.original} ${t.inNew}`}
                outcome={result.stressed}
                reserve={result.reserve_som}
                t={t}
                lang={lang}
              />
              {result.fixed ? (
                <Outcome
                  title={`${t.fixed} ${t.inNew}`}
                  outcome={result.fixed}
                  reserve={result.reserve_som}
                  t={t}
                  lang={lang}
                />
              ) : (
                <div className={css.outcomeEmpty}>
                  <h4>{t.fixed}</h4>
                  <p>{lang === "ru" ? a.fix_summary_ru : a.fix_summary_en}</p>
                </div>
              )}
            </div>

            <dl className={css.adaptation}>
              <dt>{t.damage}</dt>
              <dd>{money(result.damage_som, t, lang)}</dd>
              {result.fixed && (
                <>
                  <dt>{result.adaptation_gain_som >= 0 ? t.gain : t.gainNeg}</dt>
                  <dd>{money(Math.abs(result.adaptation_gain_som), t, lang)}</dd>
                  <dt>{t.changeCost}</dt>
                  <dd>
                    {result.change_cost_som < 0
                      ? `${money(-result.change_cost_som, t, lang)} ${t.cheaper}`
                      : money(result.change_cost_som, t, lang)}
                  </dd>
                </>
              )}
            </dl>
            <p className={css.hint}>{t.elapsed(result.elapsed_ms)}</p>
          </>
        )}
      </div>
    </div>
  );
}
