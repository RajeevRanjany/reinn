"""Accuracy metrics. Error sign: e = forecast - actual (positive = over-forecast = buyer short)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Metrics:
    n: int
    n_missing: int
    bias_mw: float | None
    mae_mw: float | None
    rmse_mw: float | None
    p50_abs_mw: float | None
    p90_abs_mw: float | None
    p99_abs_mw: float | None
    nmae: float | None
    shortfall_p90_mw: float | None
    mean_actual_mw: float | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _f(x: float) -> float | None:
    return None if x is None or math.isnan(x) else float(x)


def compute_metrics(errors: pd.Series, actuals: pd.Series) -> Metrics:
    """Metrics over rows where both error and actual are present."""
    e_all = pd.Series(errors, dtype="float64").reset_index(drop=True)
    a_all = pd.Series(actuals, dtype="float64").reset_index(drop=True)
    mask = e_all.notna() & a_all.notna()
    n_missing = int((~mask).sum())
    e = e_all[mask].to_numpy()
    a = a_all[mask].to_numpy()
    n = int(e.size)
    if n == 0:
        return Metrics(0, n_missing, None, None, None, None, None, None, None, None, None)
    abs_e = np.abs(e)
    mae = float(abs_e.mean())
    mean_a = float(a.mean())
    return Metrics(
        n=n,
        n_missing=n_missing,
        bias_mw=_f(float(e.mean())),
        mae_mw=_f(mae),
        rmse_mw=_f(float(np.sqrt(np.mean(e**2)))),
        p50_abs_mw=_f(float(np.quantile(abs_e, 0.5))),
        p90_abs_mw=_f(float(np.quantile(abs_e, 0.9))),
        p99_abs_mw=_f(float(np.quantile(abs_e, 0.99))),
        nmae=_f(mae / mean_a) if mean_a > 0 else None,
        shortfall_p90_mw=_f(float(np.quantile(np.clip(e, 0, None), 0.9))),
        mean_actual_mw=_f(mean_a),
    )


def grouped_metrics(df: pd.DataFrame, by: str) -> list[tuple[Any, Metrics]]:
    """compute_metrics per group. df needs columns error_mw, actual_mw and ``by``."""
    return [
        (key, compute_metrics(g["error_mw"], g["actual_mw"]))
        for key, g in df.groupby(by, sort=True, observed=True)
    ]


def pinball_loss(actual: pd.Series, predicted: pd.Series, tau: float) -> float | None:
    """Mean quantile (pinball) loss of ``predicted`` as the tau-quantile of ``actual``."""
    a = pd.Series(actual, dtype="float64").to_numpy()
    p = pd.Series(predicted, dtype="float64").to_numpy()
    m = ~(np.isnan(a) | np.isnan(p))
    if not m.any():
        return None
    d = a[m] - p[m]
    return float(np.mean(np.maximum(tau * d, (tau - 1) * d)))


def interval_coverage(actual: pd.Series, lower: pd.Series, upper: pd.Series) -> float | None:
    """Share of actuals inside [lower, upper] (PICP)."""
    a = pd.Series(actual, dtype="float64").to_numpy()
    lo = pd.Series(lower, dtype="float64").to_numpy()
    hi = pd.Series(upper, dtype="float64").to_numpy()
    m = ~(np.isnan(a) | np.isnan(lo) | np.isnan(hi))
    if not m.any():
        return None
    return float(np.mean((a[m] >= lo[m]) & (a[m] <= hi[m])))


def skill_score(mae_forecast: float | None, mae_baseline: float | None) -> float | None:
    """1 - MAE_f / MAE_b. >0: forecast beats the baseline; <0: it is worse."""
    if mae_forecast is None or mae_baseline is None or mae_baseline == 0:
        return None
    return 1.0 - mae_forecast / mae_baseline
