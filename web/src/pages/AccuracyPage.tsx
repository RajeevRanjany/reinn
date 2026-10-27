import {
  BiasByHour,
  ErrorHistogram,
  HorizonCurve,
  LevelBars,
} from "../components/charts/StatCharts";
import { HorizonSlider } from "../components/controls/Controls";
import { DataTable } from "../components/DataTable";
import { KpiCard } from "../components/kpi/Kpi";
import { ErrorState, Loading, Panel, SignNote } from "../components/States";
import {
  useByHorizon,
  useByHour,
  useByLevel,
  useDistribution,
  useHealth,
  useWorstMisses,
} from "../hooks/useApi";
import { useUrlState } from "../hooks/useUrlState";
import { clampHorizon } from "../lib/chartData";
import { fmtDateTime, fmtMW, fmtNum } from "../lib/format";

export function AccuracyPage() {
  const health = useHealth();
  const url = useUrlState();
  const h = clampHorizon(url.get("h"));
  const cutoff = url.get("cutoff") ?? health.data?.default_cutoff_local ?? "09:00";
  const byH = useByHorizon();
  const byHour = useByHour(h);
  const byLevel = useByLevel(h);
  const dist = useDistribution(h);
  const worst = useWorstMisses(cutoff);

  const rows = byH.data?.rows ?? [];
  const at = (x: number) => rows.find((r) => r.horizon_h === x);
  const h0 = at(0);
  const h24 = at(24);
  const h48 = at(48);
  const ramp = worst.data?.ramp_vs_non_ramp;

  return (
    <>
      <div className="page-intro">
        <h1>Accuracy Explorer</h1>
        <p>
          <em>When</em> does the forecast fail? By lead time, time of day, wind level and during
          fast ramps, across all of January 2026.
        </p>
      </div>

      <div className="kpi-row">
        <KpiCard label="MAE at 0h" value={fmtMW(h0?.mae_mw)} />
        <KpiCard label="MAE at 24h" value={fmtMW(h24?.mae_mw)} />
        <KpiCard
          label="MAE at 48h"
          value={fmtMW(h48?.mae_mw)}
          sub={
            h0?.mae_mw && h48?.mae_mw
              ? `+${fmtNum(((h48.mae_mw - h0.mae_mw) / h0.mae_mw) * 100)}% vs 0h`
              : undefined
          }
        />
        <KpiCard
          label="Bias at 24h"
          value={fmtMW(h24?.bias_mw, true)}
          tone="risk"
          info="Positive = systematically over-forecast = buyer short on average."
        />
      </div>

      <Panel
        title="Error grows with lead time"
        subtitle="MAE and P90 absolute error for every horizon 0–48h, against a persistence baseline."
      >
        {byH.isError ? (
          <ErrorState error={byH.error} />
        ) : !byH.data ? (
          <Loading />
        ) : (
          <HorizonCurve rows={rows} />
        )}
      </Panel>

      <div className="toolbar">
        <HorizonSlider value={h} onChange={(v) => url.set({ h: v })} />
        <span className="toolbar-meta">The three charts below use the {h}h-ahead forecast.</span>
      </div>

      <div className="grid-2">
        <Panel title="Bias by hour of day" subtitle="Above zero: over-forecast (short).">
          {byHour.isError ? (
            <ErrorState error={byHour.error} />
          ) : !byHour.data ? (
            <Loading height={300} />
          ) : (
            <BiasByHour rows={byHour.data.rows} />
          )}
        </Panel>
        <Panel
          title="Error distribution"
          subtitle="Red: over-forecast tail · blue: under-forecast."
        >
          {dist.isError ? (
            <ErrorState error={dist.error} />
          ) : !dist.data ? (
            <Loading height={300} />
          ) : (
            <ErrorHistogram bins={dist.data.bins} />
          )}
        </Panel>
      </div>

      <Panel
        title="Error by wind level"
        subtitle={
          byLevel.data
            ? `Forecast terciles: low < ${fmtNum((byLevel.data.meta.level_edges_mw as number[])[0])} MW ≤ mid < ${fmtNum((byLevel.data.meta.level_edges_mw as number[])[1])} MW ≤ high`
            : undefined
        }
      >
        {byLevel.isError ? (
          <ErrorState error={byLevel.error} />
        ) : !byLevel.data ? (
          <Loading height={300} />
        ) : (
          <LevelBars rows={byLevel.data.rows} />
        )}
      </Panel>

      <Panel
        title="Worst misses at decision time"
        subtitle={`Largest errors of the forecast the desk actually had at the ${cutoff} D−1 cutoff.`}
      >
        {worst.isError ? (
          <ErrorState error={worst.error} />
        ) : !worst.data ? (
          <Loading height={200} />
        ) : (
          <>
            <DataTable
              rows={worst.data.rows}
              columns={[
                { key: "t", header: "Target (UK)", render: (r) => fmtDateTime(r.target_time) },
                {
                  key: "f",
                  header: "Forecast",
                  render: (r) => fmtMW(r.forecast_mw),
                  numeric: true,
                },
                { key: "a", header: "Actual", render: (r) => fmtMW(r.actual_mw), numeric: true },
                {
                  key: "e",
                  header: "Error",
                  render: (r) => fmtMW(r.error_mw, true),
                  numeric: true,
                },
                { key: "h", header: "Lead", render: (r) => `${r.horizon_h}h`, numeric: true },
                {
                  key: "p",
                  header: "Vintage (UK)",
                  render: (r) => fmtDateTime(r.publish_time),
                },
                { key: "r", header: "Ramp?", render: (r) => (r.is_ramp ? "Yes" : "–") },
              ]}
            />
            {ramp && (
              <p className="fine">
                During ramps (|Δ3h| &gt; {fmtMW(worst.data.meta.ramp_threshold_mw as number)}) MAE
                is <strong>{fmtMW(ramp.ramp?.mae_mw)}</strong> over {ramp.ramp?.n} hours, vs{" "}
                <strong>{fmtMW(ramp.non_ramp?.mae_mw)}</strong> otherwise.
              </p>
            )}
          </>
        )}
        <SignNote />
      </Panel>
    </>
  );
}
