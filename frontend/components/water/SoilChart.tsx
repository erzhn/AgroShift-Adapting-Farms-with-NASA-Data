"use client";

// Линия истощения почвы D_r с зонами RAW/TAW (FR-3.2), по суткам.
// Ось перевёрнута: вверху почва полная, ниже — суше. Между RAW и TAW — зона стресса.

import type { DailySeries } from "../../lib/api/water";
import EChart, { baseAxes, baseTooltip, esc, tipRow, type Tokens } from "./EChart";
import { formatDate, formatNumber, type Lang, monthShort, strings } from "./strings";
import css from "./water.module.css";

interface Props {
  daily: DailySeries;
  lang: Lang;
  busy?: boolean;
}

export default function SoilChart({ daily, lang, busy }: Props) {
  const t = strings(lang);
  const mm = (v: number) => `${formatNumber(v, lang, 1)} ${t.mm}`;

  const build = (k: Tokens) => ({
    animationDuration: 200,
    grid: { left: 8, right: 48, top: 12, bottom: 4, containLabel: true },
    tooltip: {
      ...baseTooltip(k),
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: k.axis, width: 1, type: "solid" } },
      formatter: (items: { dataIndex: number }[]) => {
        const i = items[0].dataIndex;
        return `<div style="font-weight:600;margin-bottom:4px">`
          + `${esc(formatDate(daily.dates[i], lang))}</div>`
          + tipRow(k.s1, t.dr, mm(daily.dr[i]))
          + tipRow(k.text2, t.raw, mm(daily.raw[i]))
          + tipRow(k.axis, t.taw, mm(daily.taw[i]))
          + tipRow(null, t.ks, formatNumber(daily.ks[i], lang, 2))
          + (daily.irrigation[i] > 0 ? tipRow(null, t.irrigationNet, mm(daily.irrigation[i]))
            : "")
          + (daily.precip[i] > 0 ? tipRow(null, t.precip, mm(daily.precip[i])) : "");
      },
    },
    xAxis: {
      type: "category",
      data: daily.dates,
      boundaryGap: false,
      ...baseAxes(k),
      axisLabel: {
        color: k.muted, fontSize: 12,
        interval: (index: number) => daily.dates[index].slice(8, 10) === "01",
        formatter: (value: string) => monthShort(Number(value.slice(5, 7)), lang),
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value", inverse: true, min: 0,
      max: Math.ceil(Math.max(...daily.taw) / 20) * 20,
      ...baseAxes(k), axisLine: { show: false }, splitNumber: 4,
    },
    series: [
      {
        // граница стресса; она же — опора для заливки зоны стресса
        name: t.raw, type: "line", stack: "zone", showSymbol: false, data: daily.raw,
        lineStyle: { color: k.text2, width: 1 }, itemStyle: { color: k.text2 },
        endLabel: { show: true, formatter: "RAW", color: k.text2, fontSize: 12 },
      },
      {
        name: t.taw, type: "line", stack: "zone", showSymbol: false,
        data: daily.taw.map((v, i) => Math.max(v - daily.raw[i], 0)),
        lineStyle: { color: k.axis, width: 1 }, itemStyle: { color: k.axis },
        areaStyle: { color: k.critical, opacity: 0.1 },
        endLabel: { show: true, formatter: "TAW", color: k.text2, fontSize: 12 },
      },
      {
        name: t.dr, type: "line", showSymbol: false, data: daily.dr, z: 4,
        lineStyle: { color: k.s1, width: 2, join: "round", cap: "round" },
        itemStyle: { color: k.s1 },
      },
    ],
  });

  return (
    <section className={css.card}>
      <div className={css.cardHead}>
        <div>
          <h2 className={css.cardTitle}>{t.soilTitle}</h2>
          <p className={css.cardSub}>{t.soilUnit}</p>
        </div>
      </div>
      <div className={css.chartHold} data-busy={busy}>
        <ul className={css.legend}>
          <li><span className={css.keyLine} style={{ borderColor: "var(--series-1)" }} />
            {t.dr}</li>
          <li><span className={css.keyLine} style={{ borderColor: "var(--text-secondary)",
                                                     borderTopWidth: 1 }} />{t.raw}</li>
          <li><span className={css.keyBand} style={{ background: "var(--status-critical)" }} />
            {t.stressZone}</li>
        </ul>
        <EChart build={build} deps={[daily, lang]} height={240}
                ariaLabel={`${t.soilTitle}. ${t.soilUnit}`} />
      </div>
    </section>
  );
}
