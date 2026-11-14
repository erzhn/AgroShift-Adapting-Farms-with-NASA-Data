"use client";

// Тонкая обёртка над ECharts: грузит библиотеку только в браузере и следит за размером.

import type { ECharts, EChartsOption } from "echarts";
import { useEffect, useRef } from "react";

interface Props {
  option: EChartsOption;
  height?: number;
  onClickIndex?: (dataIndex: number) => void;
  ariaLabel?: string;
}

export default function EChart({ option, height = 260, onClickIndex, ariaLabel }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<ECharts | null>(null);
  const latest = useRef(option);
  const click = useRef(onClickIndex);
  useEffect(() => {
    latest.current = option;
    click.current = onClickIndex;
  });

  useEffect(() => {
    let disposed = false;
    let observer: ResizeObserver | null = null;
    import("echarts").then((echarts) => {
      if (disposed || !box.current) return;
      const instance = echarts.init(box.current, undefined, { renderer: "svg" });
      chart.current = instance;
      instance.setOption(latest.current);
      instance.getZr().on("click", (event) => {
        const [index] = instance.convertFromPixel({ gridIndex: 0 }, [event.offsetX, event.offsetY]);
        if (Number.isFinite(index)) click.current?.(Math.round(index));
      });
      observer = new ResizeObserver(() => instance.resize());
      observer.observe(box.current);
    });
    return () => {
      disposed = true;
      observer?.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, true);
  }, [option]);

  return <div ref={box} role="img" aria-label={ariaLabel} style={{ width: "100%", height }} />;
}
