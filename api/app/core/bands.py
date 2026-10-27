"""Empirical uncertainty bands ("headroom") from the forecast's own historical errors.

Errors e = F - A are bucketed by horizon and by forecast level (terciles). For a new forecast
F the band on the *actual* is [F - q90, F - q10] (since A = F - e), clipped to the physically
possible range. Headroom MW = max(q90, 0): with ~90% confidence, wind will not fall short of
the forecast by more than this.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.core.metrics import interval_coverage, pinball_loss

HORIZON_EDGES: tuple[float, ...] = (0, 6, 12, 24, 36, 48)
HORIZON_LABELS: tuple[str, ...] = ("0-6", "6-12", "12-24", "24-36", "36-48")
LEVELS: tuple[str, ...] = ("low", "mid", "high")
ALL = "all"
QUANTILES: tuple[float, ...] = (0.1, 0.5, 0.9)


def horizon_bucket(horizon_h: pd.Series) -> pd.Series:
    h = pd.Series(horizon_h, dtype="float64")
    # Right-open buckets, except the last one also includes exactly 48h.
    edges = list(HORIZON_EDGES[:-1]) + [HORIZON_EDGES[-1] + 1e-9]
    out = pd.cut(h, bins=edges, labels=list(HORIZON_LABELS), right=False)
    return out.astype("object")


def level_edges(forecast_mw: pd.Series) -> tuple[float, float]:
    f = pd.Series(forecast_mw, dtype="float64").dropna()
    return float(f.quantile(1 / 3)), float(f.quantile(2 / 3))


def level_bucket(forecast_mw: pd.Series, edges: tuple[float, float]) -> pd.Series:
    f = pd.Series(forecast_mw, dtype="float64")
    out = np.where(f < edges[0], "low", np.where(f < edges[1], "mid", "high"))
    return pd.Series(out, index=f.index, dtype="object").where(f.notna())


@dataclass(frozen=True)
class BandModel:
    table: pd.DataFrame  # columns: horizon_bucket, level_bucket, q10, q50, q90, n, source
    level_edges: tuple[float, float]
    max_actual_mw: float
    min_samples: int

    def lookup(self, horizon_b: pd.Series, level_b: pd.Series) -> pd.DataFrame:
        keys = pd.DataFrame(
            {"horizon_bucket": horizon_b.to_numpy(), "level_bucket": level_b.to_numpy()}
        )
        merged = keys.merge(self.table, how="left", on=["horizon_bucket", "level_bucket"])
        merged.index = horizon_b.index
        return merged


def fit_band_model(
    pairs: pd.DataFrame, min_samples: int = 60, edges: tuple[float, float] | None = None
) -> BandModel:
    """Fit quantiles of error per (horizon bucket x level bucket).

    pairs: columns horizon_h, forecast_mw, actual_mw.
    Cells with fewer than ``min_samples`` fall back to the horizon-only bucket, and horizon
    buckets that are themselves too small fall back to the pooled distribution.
    """
    df = pairs.dropna(subset=["horizon_h", "forecast_mw", "actual_mw"]).copy()
    df["error_mw"] = df["forecast_mw"] - df["actual_mw"]
    edges = edges or level_edges(df["forecast_mw"])
    df["horizon_bucket"] = horizon_bucket(df["horizon_h"])
    df["level_bucket"] = level_bucket(df["forecast_mw"], edges)
    df = df.dropna(subset=["horizon_bucket"])

    def q(e: pd.Series) -> dict[str, float]:
        if e.empty:
            return {"q10": np.nan, "q50": np.nan, "q90": np.nan, "n": 0}
        v = np.quantile(e.to_numpy(), QUANTILES)
        return {"q10": float(v[0]), "q50": float(v[1]), "q90": float(v[2]), "n": int(e.size)}

    pooled = q(df["error_mw"])
    rows: list[dict[str, object]] = []
    for hb in HORIZON_LABELS:
        h_err = df.loc[df["horizon_bucket"] == hb, "error_mw"]
        h_stats = q(h_err)
        h_source = "horizon"
        if h_stats["n"] < min_samples:
            h_stats, h_source = {**pooled, "n": h_stats["n"]}, "pooled"
        rows.append({"horizon_bucket": hb, "level_bucket": ALL, **h_stats, "source": h_source})
        for lb in LEVELS:
            cell = df.loc[(df["horizon_bucket"] == hb) & (df["level_bucket"] == lb), "error_mw"]
            stats = q(cell)
            source = "cell"
            if stats["n"] < min_samples:
                stats = {**h_stats, "n": stats["n"]}
                source = f"fallback:{h_source}"
            rows.append({"horizon_bucket": hb, "level_bucket": lb, **stats, "source": source})
    table = pd.DataFrame(rows)
    max_actual = float(df["actual_mw"].max()) if not df.empty else float("inf")
    return BandModel(table, edges, max_actual, min_samples)


def apply_bands(model: BandModel, horizon_h: pd.Series, forecast_mw: pd.Series) -> pd.DataFrame:
    """P10/P50/P90 of the *actual*, plus headroom, for each forecast."""
    f = pd.Series(forecast_mw, dtype="float64")
    hb = horizon_bucket(pd.Series(horizon_h, index=f.index))
    lb = level_bucket(f, model.level_edges)
    qs = model.lookup(hb, lb)

    def clip(x: pd.Series) -> pd.Series:
        return x.clip(lower=0.0, upper=model.max_actual_mw)

    return pd.DataFrame(
        {
            "horizon_bucket": hb,
            "level_bucket": lb,
            "q10": qs["q10"],
            "q50": qs["q50"],
            "q90": qs["q90"],
            "p10_mw": clip(f - qs["q90"]),
            "p50_mw": clip(f - qs["q50"]),
            "p90_mw": clip(f - qs["q10"]),
            "headroom_mw": qs["q90"].clip(lower=0.0),
        },
        index=f.index,
    )


@dataclass(frozen=True)
class BandScore:
    n: int
    coverage_p10_p90: float | None
    below_p10: float | None
    above_p90: float | None
    pinball_p10: float | None
    pinball_p50: float | None
    pinball_p90: float | None


def score_bands(actual: pd.Series, bands: pd.DataFrame) -> BandScore:
    a = pd.Series(actual, dtype="float64")
    m = a.notna() & bands["p10_mw"].notna()
    a, b = a[m], bands[m]
    if a.empty:
        return BandScore(0, None, None, None, None, None, None)
    return BandScore(
        n=int(a.size),
        coverage_p10_p90=interval_coverage(a, b["p10_mw"], b["p90_mw"]),
        below_p10=float((a < b["p10_mw"]).mean()),
        above_p90=float((a > b["p90_mw"]).mean()),
        pinball_p10=pinball_loss(a, b["p10_mw"], 0.1),
        pinball_p50=pinball_loss(a, b["p50_mw"], 0.5),
        pinball_p90=pinball_loss(a, b["p90_mw"], 0.9),
    )


def leave_one_group_out(
    fit_pairs: pd.DataFrame,
    fit_groups: pd.Series,
    eval_rows: pd.DataFrame,
    eval_groups: pd.Series,
    fit: Callable[[pd.DataFrame], BandModel],
    groups: Sequence[object] | None = None,
) -> pd.DataFrame:
    """Out-of-sample bands: for each group g, fit on rows not in g, apply to eval rows in g.

    eval_rows: columns horizon_h, forecast_mw (+ anything else, passed through).
    Returns eval_rows joined with band columns, only for groups that could be scored.
    """
    out = []
    for g in groups if groups is not None else sorted(pd.unique(eval_groups)):
        ev = eval_rows[eval_groups == g]
        if ev.empty:
            continue
        model = fit(fit_pairs[fit_groups != g])
        bands = apply_bands(model, ev["horizon_h"], ev["forecast_mw"])
        out.append(pd.concat([ev, bands], axis=1))
    if not out:
        return eval_rows.iloc[0:0]
    return pd.concat(out)
