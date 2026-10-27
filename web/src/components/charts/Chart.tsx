// Thin ECharts wrapper: registers only the pieces we use (smaller bundle) and applies
// the shared chrome (recessive grid/axes, system font, themed tooltip).
import { BarChart, LineChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts";
import { useEffect, useMemo, useRef } from "react";
import { useTokens, type Tokens } from "../../lib/theme";

echarts.use([
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  CanvasRenderer,
]);

export const FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif';

export function baseOption(k: Tokens): EChartsOption {
  return {
    backgroundColor: "transparent",
    textStyle: { fontFamily: FONT, color: k.text2 },
    animationDuration: 300,
    grid: { left: 64, right: 20, top: 60, bottom: 40, containLabel: false },
    legend: {
      top: 0,
      left: 0,
      textStyle: { color: k.text2, fontSize: 12 },
      itemWidth: 22,
      itemHeight: 10,
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: k.surface,
      borderColor: k.axis,
      textStyle: { color: k.text, fontSize: 12 },
      axisPointer: { type: "line", lineStyle: { color: k.muted, type: "dashed" } },
    },
  };
}

export function valueAxis(k: Tokens, name?: string, extra: Record<string, unknown> = {}) {
  return {
    type: "value" as const,
    name,
    nameTextStyle: { color: k.muted, fontSize: 11, align: "left" as const },
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: k.muted, fontSize: 11 },
    splitLine: { lineStyle: { color: k.grid, width: 1 } },
    ...extra,
  };
}

export function categoryAxis(k: Tokens, data: (string | number)[], name?: string) {
  return {
    type: "category" as const,
    data,
    name,
    nameLocation: "middle" as const,
    nameGap: 28,
    nameTextStyle: { color: k.muted, fontSize: 11 },
    axisLine: { lineStyle: { color: k.axis } },
    axisTick: { show: false },
    axisLabel: { color: k.muted, fontSize: 11 },
  };
}

export function timeAxis(k: Tokens) {
  return {
    type: "time" as const,
    axisLine: { lineStyle: { color: k.axis } },
    axisTick: { show: false },
    axisLabel: {
      color: k.muted,
      fontSize: 11,
      hideOverlap: true,
      formatter: (v: number) =>
        new Intl.DateTimeFormat("en-GB", {
          timeZone: "Europe/London",
          hour: "2-digit",
          minute: "2-digit",
          day: "numeric",
          month: "short",
          hour12: false,
        }).format(new Date(v)),
    },
    splitLine: { show: false },
  };
}

interface Props {
  option: (k: Tokens) => EChartsOption;
  height?: number;
  ariaLabel: string;
}

/** Owns one ECharts instance: init on mount, setOption on change, resize with the box. */
function EChart({ option, height }: { option: EChartsOption; height: number }) {
  const el = useRef<HTMLDivElement>(null);
  const inst = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!el.current) return;
    const chart = echarts.init(el.current, undefined, { renderer: "canvas" });
    inst.current = chart;
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      chart.dispose();
      inst.current = null;
    };
  }, []);

  useEffect(() => {
    inst.current?.setOption(option, { notMerge: true, lazyUpdate: true });
  }, [option]);

  return <div ref={el} style={{ height, width: "100%" }} />;
}

export function Chart({ option, height = 360, ariaLabel }: Props) {
  const k = useTokens();
  const opt = useMemo(() => option(k), [option, k]);
  return (
    <div role="img" aria-label={ariaLabel} className="chart">
      <EChart option={opt} height={height} />
    </div>
  );
}
