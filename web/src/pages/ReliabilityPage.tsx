import { CoverageByDay, SkillCurve } from "../components/charts/StatCharts";
import { DataTable } from "../components/DataTable";
import { KpiCard } from "../components/kpi/Kpi";
import { ErrorState, Loading, Panel } from "../components/States";
import { useByHorizon, useDataQuality, useHealth, useReliability } from "../hooks/useApi";
import { useUrlState } from "../hooks/useUrlState";
import { fmtDateTime, fmtMW, fmtNum, fmtPct } from "../lib/format";

export function ReliabilityPage() {
  const health = useHealth();
  const url = useUrlState();
  const cutoff = url.get("cutoff") ?? health.data?.default_cutoff_local ?? "09:00";
  const rel = useReliability(cutoff);
  const dq = useDataQuality(cutoff);
  const byH = useByHorizon();
  const r = rel.data;
  const cov = r?.decision.coverage_p10_p90;
  const calibrated = cov != null && Math.abs(cov - 0.8) <= 0.025;

  return (
    <>
      <div className="page-intro">
        <h1>Reliability &amp; Data Quality</h1>
        <p>
          Can you trust the bands and the numbers? Every score here is out-of-sample: the day being
          scored is never part of the fit.
        </p>
      </div>

      {rel.isError && <ErrorState error={rel.error} />}
      <div className="kpi-row">
        <KpiCard
          label="Band coverage (decision)"
          value={fmtPct(cov, 1)}
          sub={
            cov != null ? (
              <span>
                <span aria-hidden>{calibrated ? "✓ " : "△ "}</span>
                target 80% ·{" "}
                {calibrated
                  ? "well calibrated"
                  : cov < 0.8
                    ? "bands slightly too narrow"
                    : "bands slightly too wide"}
              </span>
            ) : undefined
          }
          info="Share of hours whose actual fell inside the P10–P90 range, with bands fitted leave-one-day-out."
        />
        <KpiCard
          label="Below P10 / above P90"
          value={r ? `${fmtPct(r.decision.below_p10)} / ${fmtPct(r.decision.above_p90)}` : "–"}
          info="Each tail should be about 10%. Below P10 means wind came in lower than the band (shortfall tail)."
        />
        <KpiCard
          label="Skill vs persistence"
          value={fmtPct(r?.skill.skill_score)}
          sub={
            r
              ? `MAE ${fmtMW(r.skill.forecast_mae_mw)} vs ${fmtMW(r.skill.persistence_mae_mw)}`
              : undefined
          }
          info={r?.skill.baseline}
        />
        <KpiCard
          label="In-sample coverage"
          value={fmtPct(r?.in_sample_coverage, 1)}
          info="For comparison only: coverage when the same data is used to fit and score. Always looks better."
        />
      </div>

      <div className="grid-2">
        <Panel title="Coverage by delivery day" subtitle="Leave-one-day-out, decision forecast.">
          {!r ? (
            !rel.isError && <Loading height={280} />
          ) : (
            <CoverageByDay rows={r.decision_by_day} />
          )}
        </Panel>
        <Panel title="Skill vs persistence by horizon" subtitle="Above 0: the forecast adds value.">
          {byH.isError ? (
            <ErrorState error={byH.error} />
          ) : !byH.data ? (
            <Loading height={280} />
          ) : (
            <SkillCurve rows={byH.data.rows} />
          )}
        </Panel>
      </div>

      {r && (
        <Panel
          title="Band scores by horizon (all vintages, 0–48h)"
          subtitle="Pinball loss scores each quantile; lower is better."
        >
          <DataTable
            rows={r.all_vintages_by_horizon_bucket}
            columns={[
              { key: "b", header: "Horizon", render: (x) => `${x.horizon_bucket}h` },
              { key: "n", header: "n", render: (x) => fmtNum(x.n), numeric: true },
              {
                key: "c",
                header: "Coverage",
                render: (x) => fmtPct(x.coverage_p10_p90, 1),
                numeric: true,
              },
              { key: "lo", header: "< P10", render: (x) => fmtPct(x.below_p10), numeric: true },
              { key: "hi", header: "> P90", render: (x) => fmtPct(x.above_p90), numeric: true },
              {
                key: "p1",
                header: "Pinball P10",
                render: (x) => fmtNum(x.pinball_p10),
                numeric: true,
              },
              {
                key: "p5",
                header: "Pinball P50",
                render: (x) => fmtNum(x.pinball_p50),
                numeric: true,
              },
              {
                key: "p9",
                header: "Pinball P90",
                render: (x) => fmtNum(x.pinball_p90),
                numeric: true,
              },
            ]}
          />
          <p className="fine">{String(r.meta.caveat)}</p>
        </Panel>
      )}

      {r && (
        <Panel
          title="Error quantiles behind the bands"
          subtitle="Error = forecast − actual, in MW. q90 is the headroom for that bucket."
        >
          <DataTable
            rows={r.band_table}
            columns={[
              { key: "h", header: "Horizon", render: (x) => `${x.horizon_bucket}h` },
              { key: "l", header: "Level", render: (x) => x.level_bucket },
              { key: "q1", header: "q10", render: (x) => fmtNum(x.q10), numeric: true },
              { key: "q5", header: "q50", render: (x) => fmtNum(x.q50), numeric: true },
              { key: "q9", header: "q90", render: (x) => fmtNum(x.q90), numeric: true },
              { key: "n", header: "n", render: (x) => fmtNum(x.n), numeric: true },
              { key: "s", header: "Source", render: (x) => x.source },
            ]}
          />
        </Panel>
      )}

      <Panel title="Data quality" subtitle="Gaps and staleness in the inputs.">
        {dq.isError ? (
          <ErrorState error={dq.error} />
        ) : !dq.data ? (
          <Loading height={160} />
        ) : (
          <>
            <ul className="dq">
              <li>
                <Status ok={dq.data.actuals.missing.length === 0} />
                Actuals: {fmtNum(dq.data.actuals.present_periods)} of{" "}
                {fmtNum(dq.data.actuals.expected_periods)} half-hours present
                {dq.data.actuals.missing.length > 0 &&
                  ` · ${dq.data.actuals.missing.length} gap(s) from ${fmtDateTime(dq.data.actuals.missing[0]?.start)}`}
              </li>
              <li>
                <Status ok={dq.data.forecasts.publication_gaps.length === 0} />
                Forecasts: {dq.data.forecasts.vintages} vintages, typically every{" "}
                {dq.data.forecasts.typical_cadence_h}h; {dq.data.forecasts.publication_gaps.length}{" "}
                gap(s) over {dq.data.forecasts.gap_threshold_h}h
                {dq.data.forecasts.off_schedule_vintages.length > 0 &&
                  ` · off-schedule: ${dq.data.forecasts.off_schedule_vintages.map((v) => fmtDateTime(v)).join(", ")}`}
              </li>
              <li>
                <Status ok={dq.data.stale_at_cutoff.days.length === 0} />
                Stale at {cutoff} cutoff (&gt; {dq.data.stale_at_cutoff.threshold_h}h old):{" "}
                {dq.data.stale_at_cutoff.days.length === 0
                  ? "none"
                  : dq.data.stale_at_cutoff.days.map((d) => d.delivery_date).join(", ")}
              </li>
              <li>
                <Status ok={dq.data.ingestion.failed_runs === 0} />
                Ingestion: {dq.data.ingestion.runs} runs, {dq.data.ingestion.failed_runs} failed,{" "}
                {dq.data.ingestion.duplicates_dropped} duplicates and{" "}
                {dq.data.ingestion.invalid_rows_dropped} invalid rows dropped
              </li>
            </ul>
            {dq.data.notes.map((n) => (
              <p key={n} className="fine">
                {n}
              </p>
            ))}
          </>
        )}
      </Panel>

      <Methodology />
    </>
  );
}

function Status({ ok }: { ok: boolean }) {
  return (
    <span className={`status ${ok ? "status-good" : "status-warn"}`}>
      <span aria-hidden>{ok ? "✓" : "!"}</span>
      <span className="sr-only">{ok ? "OK" : "Attention"}</span>
    </span>
  );
}

function Methodology() {
  return (
    <Panel title="Methodology, in plain words">
      <dl className="method">
        <dt>Decision day</dt>
        <dd>
          A purchase decided on day D−1 is for delivery day D. Decisions made 1–31 January 2026
          cover delivery days 2 January → 1 February 2026.
        </dd>
        <dt>Forecast at horizon h</dt>
        <dd>
          For a delivery time t, the latest forecast published at or before t − h. If none was
          published by then, the value is missing. We never use a later forecast.
        </dd>
        <dt>Decision forecast</dt>
        <dd>
          The latest forecast published at or before your cutoff on D−1 (default 09:00 UK time),
          used for every hour of D.
        </dd>
        <dt>Error</dt>
        <dd>
          Forecast − actual, in MW. Positive means the forecast promised more wind than arrived, so
          a buyer relying on it is short.
        </dd>
        <dt>Bands (P10–P90)</dt>
        <dd>
          From the forecast’s own past errors, grouped by lead time (0–6, 6–12, 12–24, 24–36,
          36–48h) and by forecast level (low/mid/high). Small groups fall back to lead time only. A
          well-calibrated band contains the actual 80% of the time.
        </dd>
        <dt>Headroom</dt>
        <dd>
          The 90th-percentile over-forecast for that group: wind should fall short by more than this
          in only about 1 period in 10. Summed over the day it gives MWh to cover.
        </dd>
        <dt>Persistence baseline</dt>
        <dd>
          “Tomorrow looks like the last outturn I could see at my cutoff.” Skill above zero means
          the forecast beats it.
        </dd>
      </dl>
    </Panel>
  );
}
