"""Persistence baseline: "tomorrow looks like the last outturn I could see at my cutoff"."""

from __future__ import annotations

import pandas as pd

TS = "datetime64[us, UTC]"


def known_at(actuals: pd.DataFrame, lag_min: int) -> pd.Series:
    """When each actual became known: its publish time, or end-of-period + an assumed lag."""
    fallback = actuals["target_time"] + pd.Timedelta(minutes=30 + lag_min)
    pub = actuals.get("source_publish_time")
    if pub is None:
        return fallback
    return pd.to_datetime(pub, utc=True).fillna(fallback)


def persistence_forecast(actuals: pd.DataFrame, cutoffs: pd.Series, lag_min: int = 60) -> pd.Series:
    """For each cutoff, the most recent actual whose value was known at or before it.

    actuals: columns target_time, generation_mw, [source_publish_time]
    cutoffs: tz-aware UTC timestamps (index preserved in the result).
    """
    right = pd.DataFrame(
        {
            "known_at": known_at(actuals, lag_min).astype(TS),
            "baseline_mw": actuals["generation_mw"].astype("float64"),
            "obs_time": actuals["target_time"],
        }
    ).dropna(subset=["known_at"])
    # If several actuals become known at the same moment, persistence uses the latest period.
    right = right.sort_values(["known_at", "obs_time"]).drop_duplicates("known_at", keep="last")
    left = pd.DataFrame(
        {"cutoff": pd.to_datetime(cutoffs, utc=True).astype(TS), "_i": range(len(cutoffs))}
    )
    left = left.sort_values("cutoff")
    out = pd.merge_asof(left, right, left_on="cutoff", right_on="known_at", direction="backward")
    out = out.sort_values("_i")
    return pd.Series(out["baseline_mw"].to_numpy(), index=cutoffs.index, name="baseline_mw")
