"""Data-quality checks: missing periods, publication gaps, stale decision vintages."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Gap:
    start: pd.Timestamp
    end: pd.Timestamp
    hours: float


def missing_periods(
    target_times: pd.Series, start: pd.Timestamp, end: pd.Timestamp, freq: str = "30min"
) -> list[pd.Timestamp]:
    """Expected half-hours in [start, end) with no row."""
    expected = pd.date_range(start, end, freq=freq, inclusive="left", tz="UTC")
    have = set(pd.to_datetime(target_times, utc=True))
    return [t for t in expected if t not in have]


def publication_gaps(publish_times: pd.Series, threshold_h: float) -> list[Gap]:
    """Consecutive vintages further apart than ``threshold_h``."""
    p = pd.Series(sorted(pd.to_datetime(publish_times, utc=True).unique()))
    if len(p) < 2:
        return []
    d = p.diff().dt.total_seconds() / 3600.0
    return [Gap(p[i - 1], p[i], float(d[i])) for i in d.index[d > threshold_h]]


def typical_cadence_h(publish_times: pd.Series) -> float | None:
    p = pd.Series(sorted(pd.to_datetime(publish_times, utc=True).unique()))
    if len(p) < 2:
        return None
    return float((p.diff().dt.total_seconds() / 3600.0).median())


def collapse_runs(times: list[pd.Timestamp], step: pd.Timedelta) -> list[tuple[pd.Timestamp, int]]:
    """Group consecutive timestamps into (first, count) runs, for compact reporting."""
    runs: list[tuple[pd.Timestamp, int]] = []
    for t in sorted(times):
        if runs and runs[-1][0] + step * runs[-1][1] == t:
            runs[-1] = (runs[-1][0], runs[-1][1] + 1)
        else:
            runs.append((t, 1))
    return runs
