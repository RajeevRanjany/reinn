import type { EChartsOption } from "echarts";
import { useCallback } from "react";
import type { Schemas } from "../../api/client";
import { fmtNum, fmtPct } from "../../lib/format";
import type { Tokens } from "../../lib/theme";
import { baseOption, categoryAxis, Chart, valueAxis } from "./Chart";

type AxisTip = { seriesName: string; value: number | null; marker: string; axisValue: string }[];

function rowsTip(head: (axis: string) => string, fmt: (v: number) => string) {
  return (raw: unknown) => {
    const ps = raw as AxisTip;
    if (!ps.length) return "";
    return (
      `<div style="font-weight:600;margin-bottom:4px">${head(ps[0]!.axisValue)}</div>` +
      ps
        .filter((p) => p.value !== null)
        .map(
          (p) =>
            `<div style="display:flex;gap:12px;justify-content:space-between"><span>${p.marker}${p.seriesName}</span><b>${fmt(p.value as number)}</b></div>`,
        )
        .join("")
    );
  };
}
const mw = (v: number) => `${fmtNum(v)} MW`;
export function HorizonCurve({ rows }: { rows: Schemas["HorizonRow"][] }) {
  const option = useCallback(
    (k: Tokens): EChartsOption => {
      const base = baseOption(k);
      const last = rows.length - 1;
      const lab = (name: string) => ({
        show: true,
        formatter: () => name,
        color: k.text2,
        fontSize: 11,
        position: "right" as const,
      });
      return {
        ...base,
        grid: { left: 64, right: 96, top: 60, bottom: 44 },
        tooltip: { ...(base.tooltip as object), formatter: rowsTip((h) => `${h}h ahead`, mw) },
        legend: { ...(base.legend as object), data: ["MAE", "P90 |error|", "Persistence MAE"] },
        xAxis: categoryAxis(
          k,
          rows.map((r) => r.horizon_h),
          "Hours ahead of delivery",
        ),
        yAxis: valueAxis(k, "MW", { min: 0 }),
        series: [
          {
            name: "MAE",
            type: "line",
            data: rows.map((r, i) => ({
              value: r.mae_mw,
              label: i === last ? lab("MAE") : undefined,
            })),
            symbol: "none",
            lineStyle: { color: k.forecast, width: 2 },
            itemStyle: { color: k.forecast },
          },
          {
            name: "P90 |error|",
            type: "line",
            data: rows.map((r, i) => ({
              value: r.p90_abs_mw,
              label: i === last ? lab("P90 |error|") : undefined,
            })),
            symbol: "none",
            lineStyle: { color: k.forecast, width: 2, type: "dashed" },
            itemStyle: { color: k.forecast },
          },
          {
            name: "Persistence MAE",
            type: "line",
            data: rows.map((r, i) => ({
              value: r.baseline_mae_mw,
              label: i === last ? lab("Persistence") : undefined,
            })),
            symbol: "none",
            lineStyle: { color: k.baseline, width: 2, type: "dotted" },
            itemStyle: { color: k.baseline },
          },
        ],
      };
    },
    [rows],
  );
  return (
    <Chart
      option={option}
      ariaLabel="Mean absolute error and 90th percentile absolute error by forecast horizon, with persistence baseline"
    />
  );
}

export function BiasByHour({ rows }: { rows: Schemas["HourRow"][] }) {
  const option = useCallback(
    (k: Tokens): EChartsOption => {
      const base = baseOption(k);
      return {
        ...base,
        legend: { show: false },
        tooltip: {
          ...(base.tooltip as object),
          axisPointer: { type: "shadow" },
          formatter: rowsTip(
            (h) => `${String(h).padStart(2, "0")}:00 UK time`,
            (v) => `${v > 0 ? "+" : ""}${mw(v)}`,
          ),
        },
        grid: { left: 64, right: 20, top: 24, bottom: 44 },
        xAxis: categoryAxis(
          k,
          rows.map((r) => r.hour),
          "Hour of day (UK)",
        ),
        yAxis: valueAxis(k, "bias MW"),
        series: [
          {
            name: "Bias",
            type: "bar",
            barCategoryGap: "20%",
            data: rows.map((r) => ({
              value: r.bias_mw,
              itemStyle: {
                color: (r.bias_mw ?? 0) > 0 ? k.over : k.under,
                borderRadius: (r.bias_mw ?? 0) > 0 ? [4, 4, 0, 0] : [0, 0, 4, 4],
              },
            })),
          },
        ],
      };
    },
    [rows],
  );
  return <Chart option={option} height={300} ariaLabel="Mean forecast bias by hour of day" />;
}

export function ErrorHistogram({ bins }: { bins: Schemas["HistBin"][] }) {
  const option = useCallback(
    (k: Tokens): EChartsOption => {
      const base = baseOption(k);
      const labels = bins.map((b) => fmtNum((b.lo + b.hi) / 2));
      return {
        ...base,
        legend: { show: false },
        tooltip: {
          ...(base.tooltip as object),
          axisPointer: { type: "shadow" },
          formatter: (raw: unknown) => {
            const p = (raw as { dataIndex: number }[])[0];
            const b = p ? bins[p.dataIndex] : undefined;
            if (!b) return "";
            return `<b>${fmtNum(b.lo)} to ${fmtNum(b.hi)} MW</b><br/>${b.count} periods${b.lo >= 0 ? " · over-forecast (short)" : b.hi <= 0 ? " · under-forecast (long)" : ""}`;
          },
        },
        grid: { left: 52, right: 20, top: 24, bottom: 44 },
        xAxis: categoryAxis(k, labels, "Error (MW): forecast − actual"),
        yAxis: valueAxis(k, "periods"),
        series: [
          {
            type: "bar",
            barCategoryGap: "8%",
            data: bins.map((b) => ({
              value: b.count,
              itemStyle: {
                color: b.lo >= 0 ? k.over : b.hi <= 0 ? k.under : k.muted,
                borderRadius: [3, 3, 0, 0],
              },
            })),
          },
        ],
      };
    },
    [bins],
  );
  return <Chart option={option} height={300} ariaLabel="Histogram of forecast errors" />;
}

export function LevelBars({ rows }: { rows: Schemas["LevelRow"][] }) {
  const option = useCallback(
    (k: Tokens): EChartsOption => {
      const base = baseOption(k);
      return {
        ...base,
        tooltip: {
          ...(base.tooltip as object),
          axisPointer: { type: "shadow" },
          formatter: rowsTip((l) => `${l} forecast level`, mw),
        },
        legend: { ...(base.legend as object), data: ["MAE", "Bias"] },
        grid: { left: 64, right: 20, top: 60, bottom: 44 },
        xAxis: categoryAxis(
          k,
          rows.map((r) => r.level),
          "Forecast level (tercile)",
        ),
        yAxis: valueAxis(k, "MW"),
        series: [
          {
            name: "MAE",
            type: "bar",
            data: rows.map((r) => r.mae_mw),
            itemStyle: { color: k.forecast, borderRadius: [4, 4, 0, 0] },
            barGap: "10%",
          },
          {
            name: "Bias",
            type: "bar",
            data: rows.map((r) => r.bias_mw),
            itemStyle: { color: k.actual, borderRadius: [4, 4, 0, 0] },
          },
        ],
      };
    },
    [rows],
  );
  return <Chart option={option} height={300} ariaLabel="Error by forecast wind level" />;
}

export function CoverageByDay({ rows }: { rows: Schemas["DayCoverage"][] }) {
  const option = useCallback(
    (k: Tokens): EChartsOption => {
      const base = baseOption(k);
      return {
        ...base,
        legend: { show: false },
        tooltip: {
          ...(base.tooltip as object),
          axisPointer: { type: "shadow" },
          formatter: rowsTip(
            (d) => d,
            (v) => `${fmtPct(v)} of periods inside P10–P90`,
          ),
        },
        grid: { left: 52, right: 20, top: 24, bottom: 44 },
        xAxis: categoryAxis(
          k,
          rows.map((r) => r.delivery_date.slice(5)),
          "Delivery day",
        ),
        yAxis: valueAxis(k, "coverage", {
          min: 0,
          max: 1,
          axisLabel: { color: k.muted, fontSize: 11, formatter: (v: number) => fmtPct(v) },
        }),
        series: [
          {
            name: "Coverage",
            type: "bar",
            data: rows.map((r) => r.coverage),
            itemStyle: { color: k.forecast, borderRadius: [4, 4, 0, 0] },
            markLine: {
              silent: true,
              symbol: "none",
              lineStyle: { color: k.text2, type: "dashed" },
              label: { formatter: "80% target", color: k.text2, position: "insideEndTop" },
              data: [{ yAxis: 0.8 }],
            },
          },
        ],
      };
    },
    [rows],
  );
  return (
    <Chart
      option={option}
      height={280}
      ariaLabel="Out-of-sample band coverage per delivery day versus the 80% target"
    />
  );
}

export function SkillCurve({ rows }: { rows: Schemas["HorizonRow"][] }) {
  const option = useCallback(
    (k: Tokens): EChartsOption => {
      const base = baseOption(k);
      return {
        ...base,
        legend: { show: false },
        tooltip: {
          ...(base.tooltip as object),
          formatter: rowsTip(
            (h) => `${h}h ahead`,
            (v) => (v <= -1 ? "≤ −100% (persistence far better)" : fmtPct(v)),
          ),
        },
        grid: { left: 52, right: 20, top: 24, bottom: 44 },
        xAxis: categoryAxis(
          k,
          rows.map((r) => r.horizon_h),
          "Hours ahead",
        ),
        // Persistence is near-perfect at 0h (skill ≈ −700%); cap the axis so 6–48h stays readable.
        yAxis: valueAxis(k, "skill", {
          min: -1,
          axisLabel: { color: k.muted, fontSize: 11, formatter: (v: number) => fmtPct(v) },
        }),
        series: [
          {
            name: "Skill vs persistence",
            type: "line",
            data: rows.map((r) => (r.skill === null ? null : Math.max(r.skill, -1))),
            symbol: "none",
            lineStyle: { color: k.forecast, width: 2 },
            itemStyle: { color: k.forecast },
            areaStyle: { color: k.band },
            markLine: {
              silent: true,
              symbol: "none",
              lineStyle: { color: k.text2, type: "dashed" },
              label: { formatter: "no skill", color: k.text2, position: "insideEndTop" },
              data: [{ yAxis: 0 }],
            },
          },
        ],
      };
    },
    [rows],
  );
  return (
    <Chart option={option} height={280} ariaLabel="Skill score versus persistence by horizon" />
  );
}
