import { useState } from "react";
import { buildUrl } from "../api/client";
import { ErrorChart, SeriesChart } from "../components/charts/TimeCharts";
import { DateRange, HorizonSlider, Segmented } from "../components/controls/Controls";
import { DataTable } from "../components/DataTable";
import { MetricsStrip } from "../components/kpi/Kpi";
import { ErrorState, Loading, Panel, SignNote } from "../components/States";
import { useHealth, useSeries } from "../hooks/useApi";
import { useUrlState } from "../hooks/useUrlState";
import { clampHorizon } from "../lib/chartData";
import { addDays, fmtDateTime, fmtMW } from "../lib/format";

export function SeriesPage() {
  const health = useHealth();
  const url = useUrlState();
  const days = health.data?.delivery_dates ?? [];
  const min = days[0] ?? "2026-01-02";
  const maxDay = days[days.length - 1] ?? "2026-02-01";
  const start = url.get("start") ?? min;
  const end = url.get("end") ?? addDays(maxDay, 1);
  const h = clampHorizon(url.get("h"));
  const q = useSeries(start, end, h);
  const [showError, setShowError] = useState(true);
  const [view, setView] = useState<"chart" | "table">("chart");

  if (health.isError) return <ErrorState error={health.error} />;
  const d = q.data;

  return (
    <>
      <div className="page-intro">
        <h1>Forecast vs Actual</h1>
        <p>
          For every target time, the forecast that was available <strong>{h} hours</strong> before
          delivery (the latest vintage published at least {h}h ahead), against metered outturn.
        </p>
      </div>
      <div className="toolbar">
        <DateRange
          start={start}
          end={end}
          min={min}
          max={maxDay}
          onChange={(s, e) => url.set({ start: s, end: e })}
        />
        <HorizonSlider value={h} onChange={(v) => url.set({ h: v })} />
        <a
          className="button"
          href={buildUrl("/api/v1/export.csv", { start, end, horizon_h: h })}
          download
        >
          Export CSV
        </a>
      </div>

      <MetricsStrip m={d?.metrics} />

      <Panel
        title={`Actual vs ${h}h-ahead forecast`}
        subtitle="Scroll or drag the slider below the chart to zoom. Forecasts are hourly; actuals half-hourly."
        actions={
          <>
            <label className="check">
              <input
                type="checkbox"
                checked={showError}
                onChange={(e) => setShowError(e.target.checked)}
              />
              Error chart
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
        {q.isError && <ErrorState error={q.error} />}
        {!d ? (
          !q.isError && <Loading />
        ) : view === "chart" ? (
          <div className={q.isFetching ? "refreshing" : ""}>
            <SeriesChart points={d.points} />
            {showError && <ErrorChart points={d.points} />}
          </div>
        ) : (
          <DataTable
            rows={d.points.filter((p) => p.forecast_mw !== null)}
            columns={[
              { key: "t", header: "Target (UK)", render: (r) => fmtDateTime(r.target_time) },
              { key: "a", header: "Actual", render: (r) => fmtMW(r.actual_mw), numeric: true },
              { key: "f", header: "Forecast", render: (r) => fmtMW(r.forecast_mw), numeric: true },
              { key: "e", header: "Error", render: (r) => fmtMW(r.error_mw, true), numeric: true },
              { key: "p", header: "Published (UK)", render: (r) => fmtDateTime(r.publish_time) },
            ]}
          />
        )}
        <SignNote />
      </Panel>
    </>
  );
}
