import type { EChartsOption } from "echarts";
import { useCallback } from "react";
import type { Schemas } from "../../api/client";
import { bandSeries, dense, lineSeries } from "../../lib/chartData";
import { fmtDateTime, fmtNum } from "../../lib/format";
import type { Tokens } from "../../lib/theme";
import { baseOption, Chart, timeAxis, valueAxis } from "./Chart";

type TipParam = { seriesName: string; value: [number, number | null]; marker: string };

/** Shared crosshair tooltip: local time header, one row per visible series, MW values. */
function timeTooltip(hidden: Set<string>) {
  return (raw: unknown) => {
    const ps = (raw as TipParam[]).filter((p) => !hidden.has(p.seriesName) && p.value[1] !== null);
    if (!ps.length) return "";
    const head = `<div style="font-weight:600;margin-bottom:4px">${fmtDateTime(new Date(ps[0]!.value[0]).toISOString())}</div>`;
    return (
      head +
      ps
        .map(
          (p) =>
            `<div style="display:flex;gap:12px;justify-content:space-between">` +
            `<span>${p.marker}${p.seriesName}</span><b>${fmtNum(p.value[1])} MW</b></div>`,
        )
        .join("")
    );
  };
}

export function DecisionChart({
  data,
  showVintages,
}: {
  data: Schemas["DecisionResponse"];
  showVintages: boolean;
}) {
  const option = useCallback(
    (k: Tokens): EChartsOption => {
      const { lower, width } = bandSeries(data.points);
      const p90 = data.points.map((p) => [new Date(p.target_time).getTime(), p.p90_mw]);
      const vintages = showVintages ? data.later_vintages : [];
      const base = baseOption(k);
      return {
        ...base,
        tooltip: {
          ...(base.tooltip as object),
          formatter: timeTooltip(new Set(["P10–P90 range"])),
        },
        legend: {
          ...(base.legend as object),
          data: [
            "Decision forecast",
            "P10–P90 range",
            "Actual",
            ...(vintages.length ? ["Later vintages"] : []),
          ],
        },
        xAxis: timeAxis(k),
        yAxis: valueAxis(k, "MW", { min: 0 }),
        dataZoom: [{ type: "inside" }],
        series: [
          {
            name: "P10",
            type: "line",
            data: lower,
            stack: "band",
            symbol: "none",
            lineStyle: { opacity: 0 },
            silent: true,
            itemStyle: { color: k.band },
          },
          {
            name: "P10–P90 range",
            type: "line",
            data: width,
            stack: "band",
            symbol: "none",
            lineStyle: { opacity: 0 },
            areaStyle: { color: k.band },
            itemStyle: { color: k.band },
            silent: true,
          },
          // Hidden helper so the tooltip can show the band's upper edge in MW.
          {
            name: "P90",
            type: "line",
            data: p90,
            symbol: "none",
            lineStyle: { opacity: 0 },
            itemStyle: { color: k.band },
          },
          ...vintages.map((v, i) => ({
            name: "Later vintages",
            id: `v-${i}`,
            type: "line" as const,
            data: dense(lineSeries(v.points, "forecast_mw")),
            symbol: "none",
            lineStyle: {
              color: k.vintage,
              width: 1,
              opacity: 0.35 + (0.5 * (i + 1)) / vintages.length,
            },
            itemStyle: { color: k.vintage },
            z: 1,
            tooltip: { show: false },
          })),
          {
            name: "Decision forecast",
            type: "line",
            data: dense(lineSeries(data.points, "forecast_mw")),
            symbol: "circle",
            symbolSize: 5,
            showSymbol: false,
            lineStyle: { color: k.forecast, width: 2.5 },
            itemStyle: { color: k.forecast },
            z: 5,
          },
          {
            name: "Actual",
            type: "line",
            data: dense(lineSeries(data.actuals, "actual_mw")),
            symbol: "none",
            lineStyle: { color: k.actual, width: 2, type: "dotted" },
            itemStyle: { color: k.actual },
            z: 4,
          },
        ],
      };
    },
    [data, showVintages],
  );
  return (
    <Chart
      option={option}
      height={380}
      ariaLabel="Decision forecast with P10 to P90 range, later forecast vintages and actual wind output for the delivery day"
    />
  );
}

export function SeriesChart({ points }: { points: Schemas["SeriesPoint"][] }) {
  const option = useCallback(
    (k: Tokens): EChartsOption => {
      const base = baseOption(k);
      return {
        ...base,
        tooltip: { ...(base.tooltip as object), formatter: timeTooltip(new Set()) },
        legend: { ...(base.legend as object), data: ["Forecast", "Actual"] },
        grid: { left: 64, right: 20, top: 60, bottom: 70 },
        xAxis: timeAxis(k),
        yAxis: valueAxis(k, "MW", { min: 0 }),
        dataZoom: [
          { type: "inside" },
          {
            type: "slider",
            height: 18,
            bottom: 12,
            borderColor: k.axis,
            fillerColor: k.band,
            textStyle: { color: k.muted },
          },
        ],
        series: [
          {
            name: "Forecast",
            type: "line",
            data: dense(lineSeries(points, "forecast_mw")),
            symbol: "none",
            lineStyle: { color: k.forecast, width: 2 },
            itemStyle: { color: k.forecast },
          },
          {
            name: "Actual",
            type: "line",
            data: dense(lineSeries(points, "actual_mw")),
            symbol: "none",
            lineStyle: { color: k.actual, width: 2, type: "dotted" },
            itemStyle: { color: k.actual },
          },
        ],
      };
    },
    [points],
  );
  return (
    <Chart
      option={option}
      height={380}
      ariaLabel="Actual wind generation and the forecast at the selected horizon over time"
    />
  );
}

export function ErrorChart({ points }: { points: Schemas["SeriesPoint"][] }) {
  const option = useCallback(
    (k: Tokens): EChartsOption => {
      const base = baseOption(k);
      const data = points
        .filter((p) => p.error_mw !== null)
        .map((p) => ({
          value: [new Date(p.target_time).getTime(), p.error_mw],
          itemStyle: { color: (p.error_mw ?? 0) > 0 ? k.over : k.under },
        }));
      return {
        ...base,
        legend: { show: false },
        tooltip: {
          ...(base.tooltip as object),
          formatter: (raw: unknown) => {
            const p = (raw as { value: [number, number] }[])[0];
            if (!p) return "";
            const v = p.value[1];
            return `<b>${fmtDateTime(new Date(p.value[0]).toISOString())}</b><br/>Error ${v > 0 ? "+" : ""}${fmtNum(v)} MW (${v > 0 ? "over-forecast · short" : "under-forecast · long"})`;
          },
        },
        grid: { left: 64, right: 20, top: 16, bottom: 30 },
        xAxis: timeAxis(k),
        yAxis: valueAxis(k, "error MW"),
        series: [{ name: "Error", type: "bar", data, barMaxWidth: 4 }],
      };
    },
    [points],
  );
  return (
    <Chart
      option={option}
      height={180}
      ariaLabel="Forecast error over time; bars above zero are over-forecasts"
    />
  );
}
