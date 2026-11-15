"use client";

// Лента «Вода» для главного экрана (FR-2.3): потребность против подачи по декадам,
// тревожные декады отмечены значком (FR-2.5). Синхронна со шкалой месяцев:
// ось — все 36 декад года, выбранная декада подсвечивается.
//
// Использование (страница хозяйства):
//   <WaterLane fieldIds={farm.fields.map(f => f.id)} strategy={strategyId}
//              scenario={scenarioId} selectedDecade={decade} onSelectDecade={setDecade} />

import { useEffect, useMemo, useState } from "react";

import { ApiError, type DecadeStatus, getWaterBalance, type WaterBalance }
  from "../../lib/api/water";
import EChart, { baseAxes, baseTooltip, esc, tipRow, type Tokens } from "./EChart";
import { decadeLabel, formatNumber, type Lang, monthShort, strings, useLang } from "./strings";
import css from "./water.module.css";

export interface WaterLaneProps {
  fieldIds: string[];
  strategy?: string;
  scenario?: string;
  /** Год погоды. Не задан — «типичный год» первого поля, общий для всех полей. */
  year?: number;
  selectedDecade?: number | null;
  onSelectDecade?: (decade: number) => void;
  lang?: Lang;
  height?: number;
}

interface Row {
  decade: number;
  active: boolean;
  need: number;
  received: number;
  deficitPct: number;
  status: DecadeStatus;
  failed: number;
  yearsGe20: number;
}

// Статус декады для всего хозяйства — по доле потребности, а не по худшему полю:
// красная, если воды не хватает полям с половиной потребности и больше;
// жёлтая, если затронута хотя бы треть.
const RED_SHARE = 0.5;
const WARN_SHARE = 1 / 3;

function aggregate(balances: WaterBalance[]): Row[] {
  const rows: Row[] = Array.from({ length: 36 }, (_, i) => ({
    decade: i + 1, active: false, need: 0, received: 0, deficitPct: 0, status: "ok",
    failed: 0, yearsGe20: 0,
  }));
  const deficit = new Array(36).fill(0);
  const redNeed = new Array(36).fill(0);
  const warnNeed = new Array(36).fill(0);
  for (const balance of balances) {
    for (const d of balance.season.decades) {
      const row = rows[d.decade - 1];
      row.active = true;
      row.need += d.need_gross_m3;
      row.received += d.received_m3;
      row.failed = Math.max(row.failed, d.turns_failed);
      deficit[d.decade - 1] += d.deficit_m3;
      if (d.status === "deficit_ge20") redNeed[d.decade - 1] += d.need_gross_m3;
      if (d.status !== "ok") warnNeed[d.decade - 1] += d.need_gross_m3;
    }
    for (const e of balance.ensemble.decades) {
      const row = rows[e.decade - 1];
      row.yearsGe20 = Math.max(row.yearsGe20, e.years_deficit_ge20);
    }
  }
  rows.forEach((row, i) => {
    row.deficitPct = row.need > 0 ? (deficit[i] / row.need) * 100 : 0;
    if (row.need > 0) {
      if (redNeed[i] / row.need >= RED_SHARE) row.status = "deficit_ge20";
      else if (warnNeed[i] / row.need >= WARN_SHARE) row.status = "deficit_lt20";
    }
  });
  return rows;
}

export default function WaterLane(props: WaterLaneProps) {
  const { fieldIds, strategy, scenario, year, selectedDecade, onSelectDecade, height = 190 }
    = props;
  const lang = useLang(props.lang);
  const t = strings(lang);
  const [balances, setBalances] = useState<WaterBalance[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [asTable, setAsTable] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const idsKey = fieldIds.join(",");

  useEffect(() => {
    if (!fieldIds.length) return;
    const controller = new AbortController();
    setBusy(true);
    setError(null);
    (async () => {
      const options = { strategy, scenario, year };
      // все поля считаются в погоде одного года
      const first = await getWaterBalance(fieldIds[0], options, controller.signal);
      const rest = await Promise.all(fieldIds.slice(1).map((id) =>
        getWaterBalance(id, { ...options, year: first.year }, controller.signal)));
      setBalances([first, ...rest]);
      setBusy(false);
    })().catch((e: unknown) => {
      if (controller.signal.aborted) return;
      setError(e instanceof ApiError ? e.message : t.error);
      setBusy(false);
    });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idsKey, strategy, scenario, year, attempt]);

  const rows = useMemo(() => (balances ? aggregate(balances) : []), [balances]);
  const totalYears = balances?.[0]?.ensemble.years.length ?? 30;
  const shownYear = balances?.[0]?.year;

  const statusLabel = (status: DecadeStatus) =>
    status === "deficit_ge20" ? t.deficitGe20 : status === "deficit_lt20" ? t.deficitLt20
      : t.statusOk;

  const build = (k: Tokens) => {
    const peak = Math.max(1, ...rows.map((r) => Math.max(r.need, r.received)));
    const compact = peak >= 10000;
    const axisValue = (v: number) =>
      compact ? `${formatNumber(v / 1000, lang)} ${t.thousand}` : formatNumber(v, lang);
    const flagged = rows.filter((r) => r.active && r.status !== "ok");
    return {
      animationDuration: 200,
      grid: { left: 8, right: 12, top: 18, bottom: 4, containLabel: true },
      tooltip: {
        ...baseTooltip(k),
        trigger: "axis",
        axisPointer: { type: "shadow", shadowStyle: { color: k.text, opacity: 0.06 } },
        formatter: (items: { dataIndex: number }[]) => {
          const row = rows[items[0].dataIndex];
          if (!row.active) return "";
          let html = `<div style="font-weight:600;margin-bottom:4px">`
            + `${esc(decadeLabel(row.decade, lang))}</div>`;
          html += tipRow(k.s2, t.need, `${formatNumber(row.need, lang)} ${t.m3}`);
          html += tipRow(k.s1, t.received, `${formatNumber(row.received, lang)} ${t.m3}`);
          html += tipRow(null, t.deficit, `${formatNumber(row.deficitPct, lang)} %`);
          if (row.failed) html += tipRow(null, t.turnsFailed, String(row.failed));
          if (row.status !== "ok") {
            html += `<div style="margin-top:4px;color:${k.text2}">`
              + `${esc(statusLabel(row.status))}`
              + (row.yearsGe20 ? ` · ${esc(t.yearsOf(row.yearsGe20, totalYears))}` : "")
              + `</div>`;
          }
          return html;
        },
      },
      xAxis: {
        type: "category",
        data: rows.map((r) => r.decade),
        ...baseAxes(k),
        axisLabel: {
          color: k.muted, fontSize: 12, interval: 0, hideOverlap: true,
          formatter: (_: string, index: number) =>
            index % 3 === 1 ? monthShort(Math.floor(index / 3) + 1, lang) : "",
        },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        ...baseAxes(k),
        axisLine: { show: false },
        splitNumber: 3,
        axisLabel: { color: k.muted, fontSize: 12, formatter: axisValue },
      },
      series: [
        {
          name: t.received,
          type: "bar",
          data: rows.map((r) => (r.active ? Math.round(r.received) : null)),
          barMaxWidth: 24,
          barCategoryGap: "28%",
          itemStyle: { color: k.s1, borderRadius: [4, 4, 0, 0] },
          emphasis: { itemStyle: { opacity: 0.85 } },
          markArea: selectedDecade ? {
            silent: true,
            itemStyle: { color: k.text, opacity: 0.08 },
            data: [[{ xAxis: selectedDecade - 1 }, { xAxis: selectedDecade - 1 }]],
          } : undefined,
        },
        {
          name: t.need,
          type: "line",
          step: "middle",
          data: rows.map((r) => (r.active ? Math.round(r.need) : null)),
          showSymbol: false,
          lineStyle: { color: k.s2, width: 2, join: "round", cap: "round" },
          itemStyle: { color: k.s2 },
        },
        {
          // статус: цвет + значок «!» + подпись в легенде и подсказке
          name: t.deficitGe20,
          type: "scatter",
          silent: true,
          z: 5,
          symbolSize: 18,
          data: flagged.map((r) => ({
            value: [r.decade - 1, Math.max(r.need, r.received)],
            itemStyle: {
              color: r.status === "deficit_ge20" ? k.critical : k.warning,
              borderColor: k.surface, borderWidth: 2,
            },
            label: { color: r.status === "deficit_ge20" ? "#ffffff" : "#0b0b0b" },
          })),
          label: { show: true, formatter: "!", fontSize: 11, fontWeight: 700 },
        },
      ],
    };
  };

  return (
    <section className={`${css.vizRoot} ${css.card}`} aria-busy={busy}>
      <div className={css.cardHead}>
        <div>
          <h2 className={css.cardTitle}>{t.laneTitle}</h2>
          <p className={css.cardSub}>
            {t.laneUnit}{shownYear ? ` · ${t.year.toLowerCase()} ${shownYear}` : ""}
          </p>
        </div>
        <button type="button" className={css.button} onClick={() => setAsTable((v) => !v)}
                aria-pressed={asTable}>
          {asTable ? t.chart : t.table}
        </button>
      </div>

      {error && (
        <div className={css.errorBox} role="alert">
          <span>{error}</span>
          <button type="button" className={css.button}
                  onClick={() => setAttempt((n) => n + 1)}>{t.retry}</button>
        </div>
      )}
      {!balances && !error && <p className={css.message}>{t.loading}</p>}

      {balances && !asTable && (
        <div className={css.chartHold} data-busy={busy}>
          <ul className={css.legend}>
            <li><span className={css.keyBar} style={{ background: "var(--series-1)" }} />
              {t.received}</li>
            <li><span className={css.keyLine} style={{ borderColor: "var(--series-2)" }} />
              {t.need}</li>
            <li><span className={`${css.dot} ${css.dotCritical}`}>!</span>{t.deficitGe20}</li>
            <li><span className={`${css.dot} ${css.dotWarning}`}>!</span>{t.deficitLt20}</li>
          </ul>
          <EChart build={build} deps={[rows, lang, selectedDecade]} height={height}
                  ariaLabel={`${t.laneTitle}. ${t.laneUnit}`}
                  onSelectIndex={onSelectDecade
                    ? (index) => rows[index]?.active && onSelectDecade(index + 1)
                    : undefined} />
        </div>
      )}

      {balances && asTable && (
        <div className={css.tableWrap}>
          <table className={css.table}>
            <thead>
              <tr>
                <th>{t.decade}</th>
                <th>{t.need}, {t.m3}</th>
                <th>{t.received}, {t.m3}</th>
                <th>{t.deficit}, %</th>
                <th>{t.turnsFailed}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.filter((r) => r.active).map((r) => (
                <tr key={r.decade}>
                  <td>{decadeLabel(r.decade, lang)}</td>
                  <td>{formatNumber(r.need, lang)}</td>
                  <td>{formatNumber(r.received, lang)}</td>
                  <td>{formatNumber(r.deficitPct, lang)}</td>
                  <td>{r.failed || "—"}</td>
                  <td>
                    <span className={css.status}>
                      {r.status !== "ok" && (
                        <span className={`${css.dot} ${r.status === "deficit_ge20"
                          ? css.dotCritical : css.dotWarning}`}>!</span>
                      )}
                      {statusLabel(r.status)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
