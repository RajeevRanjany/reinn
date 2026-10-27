"""Point-in-time forecast selection. The most important code in the project.

Invariant: a selected forecast is always the **latest** vintage whose ``publish_time`` is at or
before the cutoff. If none qualifies the result is missing; we never fall forward to a vintage
published after the cutoff.
"""

from __future__ import annotations

import pandas as pd

TS = "datetime64[us, UTC]"


def _as_ts(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, utc=True).astype(TS)


def select_forecast_asof(forecasts: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """Per-row cutoff selection.

    forecasts: columns target_time, publish_time, generation_mw (every vintage).
    targets:   columns target_time, cutoff (one row per target to evaluate).
    returns:   targets' columns + publish_time, forecast_mw; sorted by target_time.
    """
    left = targets.copy()
    left["target_time"] = _as_ts(left["target_time"])
    left["cutoff"] = _as_ts(left["cutoff"])
    left = left.sort_values("cutoff", kind="stable")

    right = forecasts[["target_time", "publish_time", "generation_mw"]].copy()
    right["target_time"] = _as_ts(right["target_time"])
    right["publish_time"] = _as_ts(right["publish_time"])
    right = right.dropna().sort_values("publish_time", kind="stable")

    out = pd.merge_asof(
        left,
        right,
        left_on="cutoff",
        right_on="publish_time",
        by="target_time",
        direction="backward",
        allow_exact_matches=True,  # published exactly at the cutoff counts as available
    )
    out = out.rename(columns={"generation_mw": "forecast_mw"})
    return out.sort_values("target_time", kind="stable").reset_index(drop=True)


def select_forecast_at_horizon(
    forecasts: pd.DataFrame, targets: pd.Series, horizon_h: float
) -> pd.DataFrame:
    """Horizon-h forecast for each target t: latest vintage with publish_time <= t - h."""
    t = _as_ts(pd.Series(targets, name="target_time")).reset_index(drop=True)
    left = pd.DataFrame({"target_time": t, "cutoff": t - pd.Timedelta(hours=horizon_h)})
    return select_forecast_asof(forecasts, left)


def select_decision_forecast(
    forecasts: pd.DataFrame, targets: pd.Series, cutoff: pd.Timestamp
) -> pd.DataFrame:
    """Decision-mode forecast: one shared cutoff c(D) for every target in delivery day D."""
    t = _as_ts(pd.Series(targets, name="target_time")).reset_index(drop=True)
    c = pd.Timestamp(cutoff)
    c = c.tz_localize("UTC") if c.tzinfo is None else c.tz_convert("UTC")
    left = pd.DataFrame({"target_time": t, "cutoff": c})
    return select_forecast_asof(forecasts, left)


def horizon_hours(target_time: pd.Series, publish_time: pd.Series) -> pd.Series:
    return (target_time - publish_time).dt.total_seconds() / 3600.0


def build_horizon_matrix(
    forecasts: pd.DataFrame, targets: pd.Series, horizons: range
) -> pd.DataFrame:
    """Stack select_forecast_at_horizon for many integer horizons (derived table)."""
    parts = []
    for h in horizons:
        df = select_forecast_at_horizon(forecasts, targets, float(h))
        df["horizon_h"] = h
        parts.append(df[["target_time", "horizon_h", "publish_time", "forecast_mw"]])
    return pd.concat(parts, ignore_index=True)
