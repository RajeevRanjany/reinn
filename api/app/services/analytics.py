"""Orchestration: repository reads + pure core functions -> API-ready dicts.

Responses are deterministic for a given data snapshot, so results are memoised in-process,
keyed by parameters (the snapshot is immutable while the process runs).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from app.config import Settings
from app.core import bands as B
from app.core.baseline import persistence_forecast
from app.core.metrics import compute_metrics, grouped_metrics, skill_score
from app.core.quality import (
    collapse_runs,
    missing_periods,
    publication_gaps,
    typical_cadence_h,
)
from app.core.ramps import ramp_flags
from app.core.selection import horizon_hours, select_forecast_asof
from app.repository.base import Repository

ERROR_SIGN = "forecast_minus_actual (positive = over-forecast = wind shortfall = buyer short)"


def _iso(ts: Any) -> str | None:
    if ts is None or (isinstance(ts, float) and np.isnan(ts)) or pd.isna(ts):
        return None
    return str(pd.Timestamp(ts).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"))


def _num(x: Any, nd: int = 1) -> float | None:
    if x is None or pd.isna(x):
        return None
    return round(float(x), nd)


class AnalyticsService:
    def __init__(self, repo: Repository, settings: Settings) -> None:
        self.repo = repo
        self.s = settings
        info = repo.snapshot_info()
        self.data_version = info.get("data_version", "unknown")
        self.forecast_res_h = int(info.get("forecast_resolution_min", "60")) / 60
        self.tz = settings.local_tz
        # Bind memoised methods per instance so caches die with the service.
        self.series = lru_cache(maxsize=256)(self._series)
        self.decision = lru_cache(maxsize=128)(self._decision)
        self.decision_frame = lru_cache(maxsize=8)(self._decision_frame)
        self.vintage_pairs = lru_cache(maxsize=1)(self._vintage_pairs)
        self.reliability = lru_cache(maxsize=8)(self._reliability)
        self.data_quality = lru_cache(maxsize=8)(self._data_quality)
        self.by_horizon = lru_cache(maxsize=64)(self._by_horizon)

    # ------------------------------------------------------------------ helpers
    def meta(self, **extra: Any) -> dict[str, Any]:
        return {
            "data_version": self.data_version,
            "analysis_start_utc": _iso(self.s.analysis_start_utc),
            "analysis_end_utc": _iso(self.s.analysis_end_utc),
            "error_sign": ERROR_SIGN,
            "display_timezone": self.tz,
            **extra,
        }

    def clamp(self, start: datetime | None, end: datetime | None) -> tuple[datetime, datetime]:
        lo, hi = self.s.analysis_start_utc, self.s.analysis_end_utc
        st = max(pd.Timestamp(start or lo).tz_convert("UTC"), pd.Timestamp(lo))
        en = min(pd.Timestamp(end or hi).tz_convert("UTC"), pd.Timestamp(hi))
        return st.to_pydatetime(), en.to_pydatetime()

    def delivery_days(self) -> list[date]:
        d, out = self.s.first_delivery_date, []
        while d <= self.s.last_delivery_date:
            out.append(d)
            d += timedelta(days=1)
        return out

    def local_date(self, ts: pd.Series) -> pd.Series:
        return ts.dt.tz_convert(self.tz).dt.date

    def on_forecast_grid(self, ts: pd.Series) -> pd.Series:
        """True where a target time falls on the forecast's resolution grid (e.g. :00)."""
        step = int(self.forecast_res_h * 3600)
        secs = (ts - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()
        return (secs % step) == 0

    def _matched(self, start: datetime, end: datetime, horizon_h: float) -> pd.DataFrame:
        """Actual targets with their horizon-h forecast and error (NaN where unmatched)."""
        sel = self.repo.forecast_at_horizon(start, end, horizon_h)
        act = self.repo.actuals(start, end)[["target_time", "generation_mw"]]
        df = act.rename(columns={"generation_mw": "actual_mw"}).merge(sel, on="target_time")
        df["on_grid"] = self.on_forecast_grid(df["target_time"])
        df["error_mw"] = df["forecast_mw"] - df["actual_mw"]
        df["horizon_actual_h"] = horizon_hours(df["target_time"], df["publish_time"])
        return df

    def _vintage_pairs(self) -> pd.DataFrame:
        p = self.repo.vintage_pairs(
            self.s.analysis_start_utc, self.s.analysis_end_utc, self.s.max_horizon_h
        )
        p["delivery_date"] = self.local_date(p["target_time"])
        return p

    def _fit(self, pairs: pd.DataFrame) -> B.BandModel:
        return B.fit_band_model(pairs, self.s.band_min_samples)

    # ------------------------------------------------------------------ /series
    def _series(self, start: datetime, end: datetime, horizon_h: float) -> dict[str, Any]:
        df = self._matched(start, end, horizon_h)
        g = df[df["on_grid"]]
        m = compute_metrics(g["error_mw"], g["actual_mw"])
        points = [
            {
                "target_time": _iso(r.target_time),
                "actual_mw": _num(r.actual_mw),
                "forecast_mw": _num(r.forecast_mw),
                "publish_time": _iso(r.publish_time),
                "error_mw": _num(r.error_mw),
            }
            for r in df.itertuples()
        ]
        n_targets_with_forecast_rows = int(df["forecast_mw"].notna().sum())
        return {
            "meta": self.meta(
                start=_iso(start),
                end=_iso(end),
                horizon_h=horizon_h,
                selection_rule="latest vintage with publish_time <= target_time - horizon",
                comparison="metrics use only target times where both forecast and actual exist "
                f"(forecast resolution {int(self.forecast_res_h * 60)} min, actuals 30 min)",
            ),
            "metrics": m.as_dict(),
            "n_matched": n_targets_with_forecast_rows,
            "points": points,
        }

    def series_frame(self, start: datetime, end: datetime, horizon_h: float) -> pd.DataFrame:
        return self._matched(start, end, horizon_h)

    # ------------------------------------------------------------------ decision mode
    def _decision_frame(self, cutoff_local: time) -> pd.DataFrame:
        """Decision forecast for every target in the window, each with its day's cutoff."""
        start, end = self.s.analysis_start_utc, self.s.analysis_end_utc
        fc = self.repo.forecasts(start - timedelta(days=3), end)
        targets = pd.Series(sorted(fc.loc[fc["target_time"] >= start, "target_time"].unique()))
        targets = pd.to_datetime(targets, utc=True)
        dd = self.local_date(targets)
        cut = pd.Series(
            [self.s.decision_cutoff_utc(d, cutoff_local) for d in dd], dtype="datetime64[us, UTC]"
        )
        sel = select_forecast_asof(fc, pd.DataFrame({"target_time": targets, "cutoff": cut}))
        act = self.repo.actuals(start - timedelta(days=3), end)
        sel = sel.merge(
            act[["target_time", "generation_mw"]].rename(columns={"generation_mw": "actual_mw"}),
            on="target_time",
            how="left",
        )
        sel["delivery_date"] = self.local_date(sel["target_time"])
        sel["horizon_h"] = horizon_hours(sel["target_time"], sel["publish_time"])
        sel["error_mw"] = sel["forecast_mw"] - sel["actual_mw"]
        sel["baseline_mw"] = persistence_forecast(
            act, sel["cutoff"], self.s.actual_publication_lag_min
        )
        return sel

    def _decision(self, delivery_date: date, cutoff_local: time) -> dict[str, Any]:
        day_start, day_end = self.s.local_day_bounds_utc(delivery_date)
        cutoff = self.s.decision_cutoff_utc(delivery_date, cutoff_local)
        dec = self.repo.latest_vintage_asof(day_start, day_end, cutoff)
        act = self.repo.actuals(day_start, day_end)
        warnings: list[str] = []

        # Out-of-sample bands: fit on every *other* delivery day (leave-one-day-out).
        pairs = self.vintage_pairs()
        model = self._fit(pairs[pairs["delivery_date"] != delivery_date])

        if dec.empty:
            warnings.append("No forecast vintage was published before the cutoff for this day.")
        dec["horizon_h"] = horizon_hours(dec["target_time"], dec["publish_time"])
        bands = B.apply_bands(model, dec["horizon_h"], dec["forecast_mw"])
        dec = pd.concat([dec, bands], axis=1).merge(
            act[["target_time", "generation_mw"]].rename(columns={"generation_mw": "actual_mw"}),
            on="target_time",
            how="left",
        )

        vintage_used = dec["publish_time"].max() if not dec.empty else None
        age_min = (
            (pd.Timestamp(cutoff) - vintage_used).total_seconds() / 60
            if vintage_used is not None and pd.notna(vintage_used)
            else None
        )
        if age_min is not None and age_min > self.s.stale_vintage_hours * 60:
            warnings.append(f"Decision vintage was {age_min / 60:.1f}h old at the cutoff (stale).")

        # How the forecast moved after the desk committed.
        later = self.repo.forecasts(day_start, day_end, publish_from=cutoff)
        later = later[later["publish_time"] <= later["target_time"]]
        later_vintages = []
        max_rev = None
        if not later.empty:
            joined = later.merge(dec[["target_time", "forecast_mw"]], on="target_time")
            if not joined.empty:
                rev = joined["generation_mw"] - joined["forecast_mw"]
                max_rev = float(rev.abs().max())
                last_pub = joined["publish_time"].max()
                last = joined[joined["publish_time"] == last_pub]
                net_last_rev = float((last["generation_mw"] - last["forecast_mw"]).mean())
            for pub, g in later.groupby("publish_time"):
                later_vintages.append(
                    {
                        "publish_time": _iso(pub),
                        "points": [
                            {"target_time": _iso(t), "forecast_mw": _num(v)}
                            for t, v in zip(g["target_time"], g["generation_mw"], strict=True)
                        ],
                    }
                )
        res_h = self.forecast_res_h
        matched = dec.dropna(subset=["actual_mw", "forecast_mw"])
        realised_shortfall = (
            float(np.clip(matched["forecast_mw"] - matched["actual_mw"], 0, None).sum() * res_h)
            if not matched.empty
            else None
        )
        in_band = (
            float(
                (
                    (matched["actual_mw"] >= matched["p10_mw"])
                    & (matched["actual_mw"] <= matched["p90_mw"])
                ).mean()
            )
            if not matched.empty
            else None
        )
        kpis = {
            "forecast_mwh": _num(dec["forecast_mw"].sum() * res_h, 0) if not dec.empty else None,
            "p10_mwh": _num(dec["p10_mw"].sum() * res_h, 0) if not dec.empty else None,
            "headroom_mwh_p90": _num(dec["headroom_mw"].sum() * res_h, 0)
            if not dec.empty
            else None,
            "peak_headroom_mw": _num(dec["headroom_mw"].max(), 0) if not dec.empty else None,
            "forecast_age_at_cutoff_min": _num(age_min, 0),
            "max_revision_mw_after_cutoff": _num(max_rev, 0),
            "net_revision_mw_last_vintage": _num(net_last_rev, 0) if max_rev is not None else None,
            "actual_mwh": _num(act["generation_mw"].sum() * 0.5, 0) if not act.empty else None,
            "realised_shortfall_mwh": _num(realised_shortfall, 0),
            "share_in_band": _num(in_band, 3),
        }
        summary = None
        if not dec.empty:
            hb = dec["horizon_bucket"].mode().iat[0] if dec["horizon_bucket"].notna().any() else "?"
            summary = (
                f"For {delivery_date:%d %b}, a forecast of this size at this lead time "
                f"(mostly {hb}h ahead) has historically over-forecast by up to "
                f"{kpis['peak_headroom_mw']:,.0f} MW in 1 of 10 periods. Planning to the P10 "
                f"implies about {kpis['headroom_mwh_p90']:,.0f} MWh of cover for the day."
            )
        points = [
            {
                "target_time": _iso(r.target_time),
                "publish_time": _iso(r.publish_time),
                "horizon_h": _num(r.horizon_h, 2),
                "forecast_mw": _num(r.forecast_mw),
                "p10_mw": _num(r.p10_mw),
                "p50_mw": _num(r.p50_mw),
                "p90_mw": _num(r.p90_mw),
                "headroom_mw": _num(r.headroom_mw),
                "horizon_bucket": r.horizon_bucket,
                "level_bucket": r.level_bucket,
                "actual_mw": _num(r.actual_mw),
            }
            for r in dec.itertuples()
        ]
        return {
            "meta": self.meta(
                delivery_date=delivery_date.isoformat(),
                cutoff_local=cutoff_local.strftime("%H:%M"),
                cutoff_utc=_iso(cutoff),
                vintage_used=_iso(vintage_used),
                forecast_resolution_min=int(res_h * 60),
                band_method="empirical error quantiles, horizon x level buckets, "
                "fitted leave-one-day-out (this delivery day excluded from the fit)",
                warnings=warnings,
            ),
            "kpis": kpis,
            "summary": summary,
            "points": points,
            "actuals": [
                {"target_time": _iso(t), "actual_mw": _num(v)}
                for t, v in zip(act["target_time"], act["generation_mw"], strict=True)
            ],
            "later_vintages": later_vintages,
        }

    # ------------------------------------------------------------------ accuracy
    def summary(
        self, start: datetime, end: datetime, horizon_h: float | None, mode: str, cutoff: time
    ) -> dict[str, Any]:
        if mode == "decision":
            df = self.decision_frame(cutoff)
            df = df[(df["target_time"] >= start) & (df["target_time"] < end)]
            m = compute_metrics(df["error_mw"], df["actual_mw"])
            base = compute_metrics(
                df["baseline_mw"] - df["actual_mw"],
                df["actual_mw"].where(df["forecast_mw"].notna()),
            )
            extra: dict[str, Any] = {"mode": "decision", "cutoff_local": cutoff.strftime("%H:%M")}
        else:
            h = float(horizon_h if horizon_h is not None else 24)
            df = self._matched(start, end, h)
            df = df[df["on_grid"]]
            m = compute_metrics(df["error_mw"], df["actual_mw"])
            base = None
            extra = {"mode": "horizon", "horizon_h": h}
        return {
            "meta": self.meta(start=_iso(start), end=_iso(end), **extra),
            "metrics": m.as_dict(),
            "skill_vs_persistence": skill_score(m.mae_mw, base.mae_mw) if base else None,
        }

    def _by_horizon(self, start: datetime, end: datetime) -> dict[str, Any]:
        mat = self.repo.horizon_matrix(start, end)
        act = self.repo.actuals(start, end)[["target_time", "generation_mw"]]
        df = mat.merge(act.rename(columns={"generation_mw": "actual_mw"}), on="target_time")
        df = df[df["forecast_mw"].notna()]
        df["error_mw"] = df["forecast_mw"] - df["actual_mw"]
        # Persistence baseline at the same horizon, for the skill curve.
        hist = self.repo.actuals(start - timedelta(days=3), end)
        df["baseline_mw"] = persistence_forecast(
            hist,
            df["target_time"] - pd.to_timedelta(df["horizon_h"], unit="h"),
            self.s.actual_publication_lag_min,
        ).to_numpy()
        rows = []
        for h, g in df.groupby("horizon_h"):
            m = compute_metrics(g["error_mw"], g["actual_mw"])
            b = compute_metrics(g["baseline_mw"] - g["actual_mw"], g["actual_mw"])
            rows.append(
                {
                    "horizon_h": int(h),
                    **m.as_dict(),
                    "baseline_mae_mw": b.mae_mw,
                    "skill": skill_score(m.mae_mw, b.mae_mw),
                }
            )
        return {
            "meta": self.meta(
                start=_iso(start),
                end=_iso(end),
                baseline="persistence: last actual known at target - h",
            ),
            "rows": rows,
        }

    def by_hour(self, start: datetime, end: datetime, horizon_h: float) -> dict[str, Any]:
        df = self._matched(start, end, horizon_h).dropna(subset=["forecast_mw"])
        df["hour"] = df["target_time"].dt.tz_convert(self.tz).dt.hour
        rows = [{"hour": int(k), **m.as_dict()} for k, m in grouped_metrics(df, "hour")]
        return {
            "meta": self.meta(start=_iso(start), end=_iso(end), horizon_h=horizon_h),
            "rows": rows,
        }

    def by_level(self, start: datetime, end: datetime, horizon_h: float) -> dict[str, Any]:
        df = self._matched(start, end, horizon_h).dropna(subset=["forecast_mw"])
        edges = B.level_edges(df["forecast_mw"])
        df["level"] = B.level_bucket(df["forecast_mw"], edges)
        order = {k: i for i, k in enumerate(B.LEVELS)}
        rows = sorted(
            ({"level": k, **m.as_dict()} for k, m in grouped_metrics(df, "level")),
            key=lambda r: order[r["level"]],
        )
        return {
            "meta": self.meta(
                start=_iso(start),
                end=_iso(end),
                horizon_h=horizon_h,
                level_edges_mw=[round(e) for e in edges],
            ),
            "rows": rows,
        }

    def distribution(
        self, start: datetime, end: datetime, horizon_h: float, bins: int = 30
    ) -> dict[str, Any]:
        e = self._matched(start, end, horizon_h)["error_mw"].dropna()
        if e.empty:
            return {"meta": self.meta(horizon_h=horizon_h), "bins": []}
        counts, edges = np.histogram(e, bins=bins)
        return {
            "meta": self.meta(start=_iso(start), end=_iso(end), horizon_h=horizon_h),
            "bins": [
                {
                    "lo": round(float(edges[i]), 1),
                    "hi": round(float(edges[i + 1]), 1),
                    "count": int(c),
                }
                for i, c in enumerate(counts)
            ],
        }

    def worst_misses(
        self,
        start: datetime,
        end: datetime,
        horizon_h: float | None,
        mode: str,
        cutoff: time,
        limit: int = 10,
    ) -> dict[str, Any]:
        if mode == "decision":
            df = self.decision_frame(cutoff)
            df = df[(df["target_time"] >= start) & (df["target_time"] < end)].copy()
        else:
            df = self._matched(start, end, float(horizon_h or 24))
            df["horizon_h"] = df["horizon_actual_h"]
        df = df.dropna(subset=["error_mw"])
        ramps = ramp_flags(self.repo.actuals(start - timedelta(hours=3), end))
        df = df.merge(ramps[["target_time", "is_ramp"]], on="target_time", how="left")
        top = df.reindex(df["error_mw"].abs().sort_values(ascending=False).index).head(limit)
        is_ramp = df["is_ramp"].fillna(False).astype(bool)
        ramp_stats = {
            "ramp": compute_metrics(df.loc[is_ramp, "error_mw"], df.loc[is_ramp, "actual_mw"]),
            "non_ramp": compute_metrics(
                df.loc[~is_ramp, "error_mw"], df.loc[~is_ramp, "actual_mw"]
            ),
        }
        return {
            "meta": self.meta(
                start=_iso(start),
                end=_iso(end),
                mode=mode,
                horizon_h=horizon_h,
                ramp_definition="|A(t) - A(t-3h)| above the 95th percentile",
                ramp_threshold_mw=_num(ramps.attrs.get("threshold_mw"), 0),
            ),
            "rows": [
                {
                    "target_time": _iso(r.target_time),
                    "forecast_mw": _num(r.forecast_mw),
                    "actual_mw": _num(r.actual_mw),
                    "error_mw": _num(r.error_mw),
                    "publish_time": _iso(r.publish_time),
                    "horizon_h": _num(r.horizon_h, 2),
                    "is_ramp": bool(r.is_ramp) if pd.notna(r.is_ramp) else False,
                }
                for r in top.itertuples()
            ],
            "ramp_vs_non_ramp": {k: v.as_dict() for k, v in ramp_stats.items()},
        }

    # ------------------------------------------------------------------ reliability
    def _reliability(self, cutoff_local: time) -> dict[str, Any]:
        pairs = self.vintage_pairs()
        fit = self._fit

        # 1) Decision-mode bands, leave-one-day-out.
        dec = self.decision_frame(cutoff_local).dropna(subset=["forecast_mw"])
        dec_scored = B.leave_one_group_out(
            pairs, pairs["delivery_date"], dec, dec["delivery_date"], fit
        )
        dec_score = B.score_bands(dec_scored["actual_mw"], dec_scored)
        per_day = []
        for d, g in dec_scored.groupby("delivery_date"):
            sc = B.score_bands(g["actual_mw"], g)
            per_day.append(
                {"delivery_date": d.isoformat(), "n": sc.n, "coverage": sc.coverage_p10_p90}
            )

        # 2) All vintages (0-48h), LODO, by horizon bucket.
        all_scored = B.leave_one_group_out(
            pairs, pairs["delivery_date"], pairs, pairs["delivery_date"], fit
        )
        by_bucket = []
        for hb in B.HORIZON_LABELS:
            g = all_scored[all_scored["horizon_bucket"] == hb]
            sc = B.score_bands(g["actual_mw"], g)
            by_bucket.append({"horizon_bucket": hb, **sc.__dict__})
        in_sample = B.apply_bands(fit(pairs), pairs["horizon_h"], pairs["forecast_mw"])
        in_sample_score = B.score_bands(pairs["actual_mw"], in_sample)

        # 3) Skill vs persistence in decision mode.
        dm = compute_metrics(dec["error_mw"], dec["actual_mw"])
        bm = compute_metrics(
            dec["baseline_mw"] - dec["actual_mw"],
            dec["actual_mw"].where(dec["baseline_mw"].notna()),
        )

        return {
            "meta": self.meta(
                cutoff_local=cutoff_local.strftime("%H:%M"),
                method="leave-one-day-out: for each delivery day, quantiles are fitted on all "
                "other days and scored on that day. Target coverage of [P10, P90] is 80%.",
                caveat="Other days include later days in January, which a live desk would not "
                "have had. Production uses a trailing 90-day window instead.",
            ),
            "decision": {**dec_score.__dict__, "target_coverage": 0.8},
            "decision_by_day": per_day,
            "all_vintages_by_horizon_bucket": by_bucket,
            "in_sample_coverage": in_sample_score.coverage_p10_p90,
            "skill": {
                "forecast_mae_mw": dm.mae_mw,
                "persistence_mae_mw": bm.mae_mw,
                "skill_score": skill_score(dm.mae_mw, bm.mae_mw),
                "baseline": "persistence: last actual known at the decision cutoff, held flat",
            },
            "band_table": fit(pairs).table.replace({np.nan: None}).to_dict(orient="records"),
        }

    # ------------------------------------------------------------------ data quality
    def _data_quality(self, cutoff_local: time) -> dict[str, Any]:
        start, end = self.s.analysis_start_utc, self.s.analysis_end_utc
        act = self.repo.actuals(start, end)
        missing = missing_periods(act["target_time"], pd.Timestamp(start), pd.Timestamp(end))
        pubs = self.repo.publish_times(start - timedelta(days=3), end)
        cadence = typical_cadence_h(pubs)
        threshold = max(2 * (cadence or 3), 4.5)
        gaps = publication_gaps(pubs, threshold)

        stale = []
        for d in self.delivery_days():
            cutoff = self.s.decision_cutoff_utc(d, cutoff_local)
            prior = pubs[pubs <= pd.Timestamp(cutoff)]
            last = prior.iloc[-1] if not prior.empty else None
            age_h = (
                (pd.Timestamp(cutoff) - last).total_seconds() / 3600 if last is not None else None
            )
            if age_h is None or age_h > self.s.stale_vintage_hours:
                stale.append(
                    {
                        "delivery_date": d.isoformat(),
                        "vintage_used": _iso(last),
                        "age_h": _num(age_h, 2),
                    }
                )

        runs = self.repo.ingestion_runs()
        dups = int(runs["duplicates_dropped"].fillna(0).sum()) if not runs.empty else 0
        invalid = int(runs["invalid_dropped"].fillna(0).sum()) if not runs.empty else 0
        failed = int((runs["status"] == "failed").sum()) if not runs.empty else 0
        pubs_in_window = pubs[(pubs >= pd.Timestamp(start)) & (pubs < pd.Timestamp(end))]
        usual_minute = pubs_in_window.dt.minute.mode().iat[0] if not pubs_in_window.empty else 0
        off_schedule = sorted(str(_iso(p)) for p in pubs_in_window if p.minute != usual_minute)
        return {
            "meta": self.meta(cutoff_local=cutoff_local.strftime("%H:%M")),
            "actuals": {
                "expected_periods": int(
                    (pd.Timestamp(end) - pd.Timestamp(start)) / pd.Timedelta(minutes=30)
                ),
                "present_periods": len(act),
                "missing": [
                    {"start": _iso(t), "periods": n}
                    for t, n in collapse_runs(missing, pd.Timedelta(minutes=30))
                ],
            },
            "forecasts": {
                "vintages": int(len(pubs_in_window)),
                "typical_cadence_h": cadence,
                "gap_threshold_h": threshold,
                "publication_gaps": [
                    {"from": _iso(g.start), "to": _iso(g.end), "hours": round(g.hours, 2)}
                    for g in gaps
                ],
                "off_schedule_vintages": off_schedule,
                "resolution_min": int(self.forecast_res_h * 60),
            },
            "stale_at_cutoff": {"threshold_h": self.s.stale_vintage_hours, "days": stale},
            "ingestion": {
                "runs": len(runs),
                "failed_runs": failed,
                "duplicates_dropped": dups,
                "invalid_rows_dropped": invalid,
            },
            "notes": [
                "WINDFOR is hourly; FUELHH is half-hourly. Accuracy is computed only at target "
                "times present in both (the top of each hour). Forecasts are never interpolated.",
                "FUELHH WIND is metered output of BM wind units after any curtailment (accepted "
                "bids), while WINDFOR forecasts generation before balancing actions. Part of the "
                "positive bias, especially at high wind, is likely this definitional gap.",
            ],
        }
