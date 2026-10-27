"""Parse raw Elexon rows into typed, validated, de-duplicated frames (all times UTC)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

TS = "datetime64[us, UTC]"


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Normalised:
    frame: pd.DataFrame
    rows_received: int
    duplicates_dropped: int
    invalid_dropped: int


def _ts(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, utc=True).astype(TS)


def normalise_fuelhh(rows: list[dict[str, Any]]) -> Normalised:
    cols = [
        "target_time",
        "settlement_date",
        "settlement_period",
        "generation_mw",
        "source_publish_time",
    ]
    if not rows:
        return Normalised(pd.DataFrame(columns=cols), 0, 0, 0)
    raw = pd.DataFrame(rows)
    missing = {"startTime", "generation", "settlementDate", "settlementPeriod"} - set(raw.columns)
    if missing:
        raise ValidationError(f"FUELHH rows missing fields: {sorted(missing)}")
    if "fuelType" in raw.columns:
        raw = raw[raw["fuelType"] == "WIND"]
    df = pd.DataFrame(
        {
            "target_time": _ts(raw["startTime"]),
            "settlement_date": pd.to_datetime(raw["settlementDate"]).dt.date,
            "settlement_period": pd.to_numeric(raw["settlementPeriod"], errors="coerce"),
            "generation_mw": pd.to_numeric(raw["generation"], errors="coerce"),
            "source_publish_time": _ts(raw["publishTime"]) if "publishTime" in raw else pd.NaT,
        }
    )
    before = len(df)
    df = df.dropna(subset=["target_time", "generation_mw", "settlement_period"])
    df = df[df["generation_mw"] >= 0]
    invalid = before - len(df)
    # Revisions: keep the most recently published value per target.
    df = df.sort_values(["target_time", "source_publish_time"], na_position="first")
    deduped = df.drop_duplicates("target_time", keep="last")
    deduped = deduped.astype({"settlement_period": "int16"}).reset_index(drop=True)
    return Normalised(deduped, len(rows), len(df) - len(deduped), invalid)


def normalise_windfor(rows: list[dict[str, Any]]) -> Normalised:
    cols = ["target_time", "publish_time", "generation_mw"]
    if not rows:
        return Normalised(pd.DataFrame(columns=cols), 0, 0, 0)
    raw = pd.DataFrame(rows)
    missing = {"startTime", "publishTime", "generation"} - set(raw.columns)
    if missing:
        raise ValidationError(f"WINDFOR rows missing fields: {sorted(missing)}")
    df = pd.DataFrame(
        {
            "target_time": _ts(raw["startTime"]),
            "publish_time": _ts(raw["publishTime"]),
            "generation_mw": pd.to_numeric(raw["generation"], errors="coerce"),
        }
    )
    before = len(df)
    df = df.dropna()
    df = df[df["generation_mw"] >= 0]
    invalid = before - len(df)
    deduped = df.drop_duplicates(["target_time", "publish_time"], keep="last")
    deduped = deduped.sort_values(["target_time", "publish_time"]).reset_index(drop=True)
    return Normalised(deduped, len(rows), len(df) - len(deduped), invalid)
