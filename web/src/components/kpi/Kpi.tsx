import type { ReactNode } from "react";
import type { Metrics } from "../../api/client";
import { fmtMW, fmtPct } from "../../lib/format";
import { InfoTip } from "../controls/InfoTip";

export function KpiCard({
  label,
  value,
  sub,
  info,
  tone,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  info?: string;
  tone?: "risk" | "neutral";
}) {
  return (
    <div className={`kpi ${tone === "risk" ? "kpi-risk" : ""}`}>
      <div className="kpi-label">
        {label}
        {info && <InfoTip text={info} />}
      </div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

export const METRIC_DEFS: Record<string, string> = {
  bias: "Mean of (forecast − actual). Positive = forecast too high on average = buyer short.",
  mae: "Mean absolute error: the typical size of a miss, in MW.",
  rmse: "Root mean squared error: like MAE but penalises big misses more.",
  p90: "90% of periods had an absolute error below this.",
  nmae: "MAE divided by mean actual output, so periods with different wind levels compare.",
  shortfall: "90th percentile of over-forecast (shortfall) only — the procurement-relevant tail.",
  n: "Number of target times with both a forecast and an actual.",
};

export function MetricsStrip({ m, skill }: { m: Metrics | undefined; skill?: number | null }) {
  return (
    <div className="kpi-row">
      <KpiCard label="Bias" value={fmtMW(m?.bias_mw, true)} info={METRIC_DEFS.bias} />
      <KpiCard label="MAE" value={fmtMW(m?.mae_mw)} info={METRIC_DEFS.mae} />
      <KpiCard label="RMSE" value={fmtMW(m?.rmse_mw)} info={METRIC_DEFS.rmse} />
      <KpiCard label="P90 |error|" value={fmtMW(m?.p90_abs_mw)} info={METRIC_DEFS.p90} />
      <KpiCard label="nMAE" value={fmtPct(m?.nmae, 1)} info={METRIC_DEFS.nmae} />
      <KpiCard
        label="Shortfall P90"
        value={fmtMW(m?.shortfall_p90_mw)}
        info={METRIC_DEFS.shortfall}
        tone="risk"
      />
      {skill !== undefined ? (
        <KpiCard
          label="Skill vs persistence"
          value={fmtPct(skill, 0)}
          info="1 − MAE(forecast) / MAE(persistence). Above 0 means the forecast beats 'tomorrow looks like now'."
        />
      ) : (
        <KpiCard
          label="Samples"
          value={m ? m.n.toLocaleString("en-GB") : "–"}
          info={METRIC_DEFS.n}
        />
      )}
    </div>
  );
}
