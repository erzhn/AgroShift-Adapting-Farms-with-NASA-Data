"use client";

// График сезона (FR-3.2): приход воды (полив + осадки) против потребности культуры ETc
// по декадам. Красная полоса под линией ETc — недобор воды (ETc − ETa). ET0 — тихий фон.
// Одна ось, одна единица: мм за декаду.

import { useState } from "react";

import type { FieldSeason } from "../../lib/api/water";
import EChart, { baseAxes, baseTooltip, esc, tipRow, type Tokens } from "./EChart";
import { decadeLabel, formatNumber, type Lang, strings } from "./strings";
import css from "./water.module.css";

interface Props {
  season: FieldSeason;
  lang: Lang;
  busy?: boolean;
}

export default function SeasonChart({ season, lang, busy }: Props) {
  const t = strings(lang);
  const [asTable, setAsTable] = useState(false);
  const rows = season.decades;
  const mm = (v: number) => `${formatNumber(v, lang, 1)} ${t.mm}`;

  const build = (k: Tokens) => ({
    animationDuration: 200,
    grid: { left: 8, right: 12, top: 16, bottom: 4, containLabel: true },
    tooltip: {
      ...baseTooltip(k),
      trigger: "axis",
      axisPointer: { type: "shadow", shadowStyle: { color: k.text, opacity: 0.06 } },
      formatter: (items: { dataIndex: number }[]) => {
        const d = rows[items[0].dataIndex];
        return `<div style="font-weight:600;margin-bottom:4px">`
          + `${esc(decadeLabel(d.decade, lang))} · ${esc(t.stageNames[d.stage])}</div>`
          + tipRow(k.s2, t.etc, mm(d.etc_mm))
          + tipRow(null, t.eta, mm(d.eta_mm))
          + tipRow(k.critical, t.shortfall, mm(Math.max(d.etc_mm - d.eta_mm, 0)))
          + tipRow(k.s1, t.irrigationNet, mm(d.irrigation_net_mm))
          + tipRow(k.s3, t.precip, mm(d.precip_mm))
          + tipRow(k.muted, t.et0, mm(d.et0_mm))
          + tipRow(null, t.ks, formatNumber(d.ks_avg, lang, 2));
      },
    },
    xAxis: {
      type: "category",
      data: rows.map((d) => decadeLabel(d.decade, lang)),
      ...baseAxes(k),
      axisLabel: { color: k.muted, fontSize: 12, hideOverlap: true },
      splitLine: { show: false },
    },
    yAxis: { type: "value", ...baseAxes(k), axisLine: { show: false }, splitNumber: 4 },
    series: [
      {
        name: t.irrigationNet, type: "bar", stack: "in", barMaxWidth: 24,
        data: rows.map((d) => d.irrigation_net_mm),
        // зазор цветом поверхности отделяет сегменты столбика
        itemStyle: { color: k.s1, borderColor: k.surface, borderWidth: 1 },
      },
      {
        name: t.precip, type: "bar", stack: "in", barMaxWidth: 24,
        data: rows.map((d) => d.precip_mm),
        itemStyle: { color: k.s3, borderColor: k.surface, borderWidth: 1,
                     borderRadius: [4, 4, 0, 0] },
      },
      {
        // невидимая опора: полоса недобора рисуется между ETa и ETc
        name: t.eta, type: "line", stack: "et", silent: true, showSymbol: false,
        data: rows.map((d) => d.eta_mm), lineStyle: { opacity: 0 },
      },
      {
        name: t.shortfall, type: "line", stack: "et", silent: true, showSymbol: false,
        data: rows.map((d) => Math.max(d.etc_mm - d.eta_mm, 0)),
        lineStyle: { opacity: 0 }, areaStyle: { color: k.critical, opacity: 0.28 },
      },
      {
        name: t.et0, type: "line", showSymbol: false, data: rows.map((d) => d.et0_mm),
        lineStyle: { color: k.muted, width: 1.5 }, itemStyle: { color: k.muted },
      },
      {
        name: t.etc, type: "line", showSymbol: false, data: rows.map((d) => d.etc_mm),
        lineStyle: { color: k.s2, width: 2, join: "round", cap: "round" },
        itemStyle: { color: k.s2 },
      },
    ],
  });

  return (
    <section className={css.card}>
      <div className={css.cardHead}>
        <div>
          <h2 className={css.cardTitle}>{t.seasonTitle}</h2>
          <p className={css.cardSub}>{t.seasonUnit}</p>
        </div>
        <button type="button" className={css.button} onClick={() => setAsTable((v) => !v)}
                aria-pressed={asTable}>
          {asTable ? t.chart : t.table}
        </button>
      </div>

      {!asTable ? (
        <div className={css.chartHold} data-busy={busy}>
          <ul className={css.legend}>
            <li><span className={css.keyBar} style={{ background: "var(--series-1)" }} />
              {t.irrigationNet}</li>
            <li><span className={css.keyBar} style={{ background: "var(--series-3)" }} />
              {t.precip}</li>
            <li><span className={css.keyLine} style={{ borderColor: "var(--series-2)" }} />
              {t.etc}</li>
            <li><span className={css.keyBand} style={{ background: "var(--status-critical)" }} />
              {t.shortfall}</li>
            <li><span className={css.keyLine} style={{ borderColor: "var(--text-muted)" }} />
              {t.et0}</li>
          </ul>
          <EChart build={build} deps={[season, lang]} height={300}
                  ariaLabel={`${t.seasonTitle}, ${t.seasonUnit}`} />
        </div>
      ) : (
        <div className={css.tableWrap}>
          <table className={css.table}>
            <thead>
              <tr>
                <th>{t.decade}</th>
                <th>ET0</th>
                <th>ETc</th>
                <th>ETa</th>
                <th>{t.precip}</th>
                <th>{t.irrigationNet}</th>
                <th>K_s</th>
                <th>D_r</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.decade}>
                  <td>{decadeLabel(d.decade, lang)}</td>
                  <td>{formatNumber(d.et0_mm, lang, 1)}</td>
                  <td>{formatNumber(d.etc_mm, lang, 1)}</td>
                  <td>{formatNumber(d.eta_mm, lang, 1)}</td>
                  <td>{formatNumber(d.precip_mm, lang, 1)}</td>
                  <td>{formatNumber(d.irrigation_net_mm, lang, 1)}</td>
                  <td>{formatNumber(d.ks_avg, lang, 2)}</td>
                  <td>{formatNumber(d.dr_end_mm, lang, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
