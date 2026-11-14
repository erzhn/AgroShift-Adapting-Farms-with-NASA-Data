"use client";

// Тонкая обёртка над ECharts: подключает только нужные модули (вес бандла, NFR-1),
// берёт цвета из CSS-переменных темы и перерисовывается при смене темы и размера.

import { BarChart, LineChart, ScatterChart } from "echarts/charts";
import { GridComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent }
  from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

echarts.use([BarChart, LineChart, ScatterChart, GridComponent, MarkAreaComponent,
  MarkLineComponent, TooltipComponent, CanvasRenderer]);

export interface Tokens {
  surface: string;
  text: string;
  text2: string;
  muted: string;
  grid: string;
  axis: string;
  s1: string;
  s2: string;
  s3: string;
  good: string;
  warning: string;
  critical: string;
}

const TOKEN_VARS: Record<keyof Tokens, string> = {
  surface: "--surface-1", text: "--text-primary", text2: "--text-secondary",
  muted: "--text-muted", grid: "--grid", axis: "--axis",
  s1: "--series-1", s2: "--series-2", s3: "--series-3",
  good: "--status-good", warning: "--status-warning", critical: "--status-critical",
};

export function readTokens(el: HTMLElement): Tokens {
  const style = getComputedStyle(el);
  const out = {} as Tokens;
  for (const key of Object.keys(TOKEN_VARS) as (keyof Tokens)[]) {
    out[key] = style.getPropertyValue(TOKEN_VARS[key]).trim() || "#888888";
  }
  return out;
}

/** Общие части опций: оси и сетка — тихие сплошные волосяные линии. */
export function baseAxes(t: Tokens) {
  return {
    axisLine: { lineStyle: { color: t.axis } },
    axisTick: { show: false },
    axisLabel: { color: t.muted, fontSize: 12 },
    splitLine: { lineStyle: { color: t.grid, type: "solid" as const, width: 1 } },
  };
}

export function baseTooltip(t: Tokens) {
  return {
    backgroundColor: t.surface,
    borderColor: t.axis,
    borderWidth: 1,
    padding: [8, 10],
    textStyle: { color: t.text, fontSize: 13 },
    confine: true,
  };
}

/** Экранирует текст для HTML-подсказки (имена приходят из API). */
export function esc(value: unknown): string {
  return String(value).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));
}

/** Строка подсказки: ключ-штрих цветом серии, подпись, затем значение (оно главное). */
export function tipRow(color: string | null, label: string, value: string): string {
  const key = color
    ? `<span style="display:inline-block;width:12px;border-top:2px solid ${color};`
      + `margin-right:6px;vertical-align:middle"></span>`
    : `<span style="display:inline-block;width:18px"></span>`;
  return `<div style="display:flex;justify-content:space-between;gap:16px">`
    + `<span>${key}${esc(label)}</span><strong>${esc(value)}</strong></div>`;
}

interface Props {
  build: (tokens: Tokens) => Record<string, unknown>;
  deps: unknown[];
  height: number;
  ariaLabel: string;
  onSelectIndex?: (dataIndex: number) => void;
}

export default function EChart({ build, deps, height, ariaLabel, onSelectIndex }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const selectRef = useRef(onSelectIndex);
  selectRef.current = onSelectIndex;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart = echarts.init(el, undefined, { renderer: "canvas" });
    const render = () => chart.setOption(build(readTokens(el)), true);
    render();

    const resize = new ResizeObserver(() => chart.resize());
    resize.observe(el);
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", render);
    const theme = new MutationObserver(render);
    theme.observe(document.documentElement,
      { attributes: true, attributeFilter: ["data-theme", "class"] });

    // клик по любой точке графика выбирает ближайшую категорию по оси X
    chart.getZr().on("click", (event: { offsetX: number; offsetY: number }) => {
      if (!selectRef.current) return;
      const point = [event.offsetX, event.offsetY];
      if (!chart.containPixel({ gridIndex: 0 }, point)) return;
      const [x] = chart.convertFromPixel({ gridIndex: 0 }, point) as number[];
      selectRef.current(Math.round(x));
    });

    return () => {
      resize.disconnect();
      media.removeEventListener("change", render);
      theme.disconnect();
      chart.dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ height, width: "100%" }} />;
}
