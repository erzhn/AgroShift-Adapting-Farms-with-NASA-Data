"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { useTranslation } from "@/src/i18n";

type DecadeSummary = {
  decade: number;
  supply_head_m3: number | null;
  demand_head_before_m3: number;
  demand_head_after_m3: number;
};

export default function DemandChart({
  data,
  loading,
}: {
  data: DecadeSummary[];
  loading: boolean;
}) {
  const element = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const { t } = useTranslation();

  useEffect(() => {
    if (!element.current) return;
    chart.current = echarts.init(element.current, undefined, { renderer: "canvas" });
    const resize = () => chart.current?.resize();
    const observer = new ResizeObserver(resize);
    observer.observe(element.current);
    return () => {
      observer.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    const instance = chart.current;
    if (!instance) return;
    instance.setOption({
      animationDuration: 350,
      grid: { left: 54, right: 20, top: 24, bottom: 42 },
      tooltip: {
        trigger: "axis",
        valueFormatter: (value: number | string) => `${Math.round(Number(value)).toLocaleString()} m³`,
      },
      legend: { bottom: 0, icon: "circle", itemWidth: 8, itemHeight: 8, textStyle: { color: "#718078" } },
      xAxis: {
        type: "category",
        data: data.map((item) => item.decade),
        axisLabel: { color: "#829088", fontSize: 10, interval: 2 },
        axisLine: { lineStyle: { color: "#e6e9e2" } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        name: "m³",
        nameTextStyle: { color: "#8c9890", padding: [0, 0, 6, 0] },
        axisLabel: { color: "#829088", fontSize: 10 },
        splitLine: { lineStyle: { color: "#eef0eb" } },
      },
      series: [
        {
          name: t("supply"),
          type: "line",
          data: data.map((item) => item.supply_head_m3),
          smooth: 0.25,
          symbol: "none",
          lineStyle: { color: "#3976b8", width: 2 },
          areaStyle: { color: "rgba(57,118,184,0.08)" },
        },
        {
          name: t("before"),
          type: "line",
          data: data.map((item) => item.demand_head_before_m3),
          smooth: 0.25,
          symbol: "none",
          lineStyle: { color: "#d98649", width: 2, type: "dashed" },
        },
        {
          name: t("after"),
          type: "line",
          data: data.map((item) => item.demand_head_after_m3),
          smooth: 0.25,
          symbol: "none",
          lineStyle: { color: "#159b85", width: 3 },
          areaStyle: { color: "rgba(21,155,133,0.10)" },
        },
      ],
      graphic: loading
        ? [{ type: "text", left: "center", top: "middle", style: { text: t("loading"), fill: "#829088" } }]
        : [],
    });
  }, [data, loading, t]);

  return <div className="chart-canvas" ref={element} role="img" aria-label={t("demandChart")} />;
}
