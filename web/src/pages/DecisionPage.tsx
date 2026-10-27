import { useState } from "react";
import { DecisionChart } from "../components/charts/TimeCharts";
import { CutoffPicker, DayPicker, Segmented } from "../components/controls/Controls";
import { DataTable } from "../components/DataTable";
import { KpiCard } from "../components/kpi/Kpi";
import { ErrorState, Loading, Panel, SignNote } from "../components/States";
import { useDecision, useHealth } from "../hooks/useApi";
import { useUrlState } from "../hooks/useUrlState";
import { fmtDateTime, fmtDay, fmtEnergy, fmtMinutes, fmtMW, fmtPct, fmtTime } from "../lib/format";

const DEFAULT_DAY = "2026-01-15";

export function DecisionPage() {
  const health = useHealth();
  const url = useUrlState();
  const days = health.data?.delivery_dates ?? [];
  const day =
    url.get("date") ?? (days.includes(DEFAULT_DAY) ? DEFAULT_DAY : (days[0] ?? undefined));
  const cutoff = url.get("cutoff") ?? health.data?.default_cutoff_local ?? "09:00";
  const q = useDecision(day, cutoff);
  const [view, setView] = useState<"chart" | "table">("chart");
  const [showVintages, setShowVintages] = useState(true);

  if (health.isError) return <ErrorState error={health.error} />;
  if (!day) return <Loading />;
  const d = q.data;
  const k = d?.kpis;
  const warnings = (d?.meta.warnings as string[] | undefined) ?? [];

  return (
    <>
      <div className="page-intro">
        <h1>Decision Mode</h1>
        <p>
          What the wind forecast said at the moment you had to commit volume for{" "}
          <strong>{fmtDay(day)}</strong>, how wrong forecasts like it have been, and how much cover
          that implies. Nothing published after the cutoff is used.
        </p>
      </div>

      <div className="toolbar">
        <DayPicker value={day} days={days} onChange={(v) => url.set({ date: v })} />
        <CutoffPicker value={cutoff} onChange={(v) => url.set({ cutoff: v })} />
        {d && (
          <div className="toolbar-meta">
            Cutoff <strong>{fmtDateTime(String(d.meta.cutoff_utc))}</strong> · vintage used{" "}
            <strong>{fmtDateTime(String(d.meta.vintage_used))}</strong>
          </div>
        )}
      </div>

      {warnings.map((w) => (
        <div key={w} className="banner banner-warn" role="status">
          <span aria-hidden>⚠</span> {w}
        </div>
      ))}

      {q.isError && <ErrorState error={q.error} />}

      <div className="kpi-row">
        <KpiCard
          label="Forecast energy"
          value={fmtEnergy(k?.forecast_mwh)}
          sub={k ? `P10 ${fmtEnergy(k.p10_mwh)}` : undefined}
          info="Sum of the decision forecast over the delivery day."
        />
        <KpiCard
          label="Headroom (P90 shortfall)"
          value={fmtEnergy(k?.headroom_mwh_p90)}
          sub={k ? `peak ${fmtMW(k.peak_headroom_mw)}` : undefined}
          tone="risk"
          info="Energy to cover if wind under-delivers at the historical 90th-percentile over-forecast for this horizon and wind level. Per period: max(q90 of error, 0)."
        />
        <KpiCard
          label="Forecast age at cutoff"
          value={fmtMinutes(k?.forecast_age_at_cutoff_min)}
          info="How old the latest available forecast vintage was when you decided."
        />
        <KpiCard
          label="Max revision after cutoff"
          value={fmtMW(k?.max_revision_mw_after_cutoff)}
          sub={
            k?.net_revision_mw_last_vintage != null
              ? `last vintage ${fmtMW(k.net_revision_mw_last_vintage, true)} avg`
              : undefined
          }
          info="Largest change, at any hour, between the decision forecast and any later vintage."
        />
        <KpiCard
          label="Outturn"
          value={fmtEnergy(k?.actual_mwh)}
          sub={
            k?.share_in_band != null ? `${fmtPct(k.share_in_band)} of hours in P10–P90` : undefined
          }
          info="Metered wind generation (FUELHH) for the day, once known."
        />
      </div>

      {d?.summary && <p className="summary">{d.summary}</p>}

      <Panel
        title="Forecast at decision time vs what happened"
        subtitle={
          <>
            Solid: forecast at cutoff · shaded: P10–P90 out-of-sample range · dotted: actual · grey:
            vintages published after you committed.
          </>
        }
        actions={
          <>
            <label className="check">
              <input
                type="checkbox"
                checked={showVintages}
                onChange={(e) => setShowVintages(e.target.checked)}
              />
              Later vintages
            </label>
            <Segmented
              label="View"
              value={view}
              onChange={setView}
              options={[
                { value: "chart", label: "Chart" },
                { value: "table", label: "Table" },
              ]}
            />
          </>
        }
      >
        {!d ? (
          q.isError ? null : (
            <Loading />
          )
        ) : view === "chart" ? (
          <div className={q.isFetching ? "refreshing" : ""}>
            <DecisionChart data={d} showVintages={showVintages} />
          </div>
        ) : (
          <DataTable
            rows={d.points}
            columns={[
              { key: "t", header: "Hour (UK)", render: (r) => fmtTime(r.target_time) },
              { key: "h", header: "Lead time", render: (r) => `${r.horizon_h}h`, numeric: true },
              { key: "f", header: "Forecast", render: (r) => fmtMW(r.forecast_mw), numeric: true },
              { key: "p10", header: "P10", render: (r) => fmtMW(r.p10_mw), numeric: true },
              { key: "p90", header: "P90", render: (r) => fmtMW(r.p90_mw), numeric: true },
              { key: "hr", header: "Headroom", render: (r) => fmtMW(r.headroom_mw), numeric: true },
              { key: "a", header: "Actual", render: (r) => fmtMW(r.actual_mw), numeric: true },
              {
                key: "b",
                header: "Bucket",
                render: (r) => `${r.horizon_bucket}h · ${r.level_bucket}`,
              },
            ]}
          />
        )}
        <SignNote />
        {d && <p className="fine">{String(d.meta.band_method)}.</p>}
      </Panel>
    </>
  );
}
