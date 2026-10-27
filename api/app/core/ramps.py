"""Ramp detection on outturn: periods where wind changed unusually fast."""

from __future__ import annotations

import pandas as pd


def ramp_flags(actuals: pd.DataFrame, window_h: float = 3.0, pct: float = 0.95) -> pd.DataFrame:
    """Flag targets where |A(t) - A(t - window)| exceeds the ``pct`` quantile of such changes.

    actuals: columns target_time, generation_mw. Returns target_time, ramp_mw, is_ramp.
    """
    a = actuals[["target_time", "generation_mw"]].sort_values("target_time")
    s = a.set_index("target_time")["generation_mw"].astype("float64")
    prior = s.reindex(s.index - pd.Timedelta(hours=window_h)).to_numpy()
    change = s.to_numpy() - prior
    out = pd.DataFrame({"target_time": s.index, "ramp_mw": change})
    threshold = out["ramp_mw"].abs().quantile(pct)
    out["is_ramp"] = out["ramp_mw"].abs() > threshold
    out.attrs["threshold_mw"] = float(threshold) if pd.notna(threshold) else None
    return out.reset_index(drop=True)
