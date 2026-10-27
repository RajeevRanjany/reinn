"""DuckDB adapter: the MVP storage backend.

Timestamps are stored as naive ``TIMESTAMP`` values in UTC and re-localised to UTC on the way
out, so DuckDB's session time zone can never shift them.
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.repository.base import Repository

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingestion_run (
    run_id          VARCHAR PRIMARY KEY,
    dataset         VARCHAR NOT NULL,
    window_from     TIMESTAMP NOT NULL,
    window_to       TIMESTAMP NOT NULL,
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    rows_received   INTEGER,
    rows_upserted   INTEGER,
    duplicates_dropped INTEGER,
    invalid_dropped INTEGER,
    status          VARCHAR NOT NULL,
    error           VARCHAR
);
CREATE TABLE IF NOT EXISTS actual_generation (
    target_time         TIMESTAMP PRIMARY KEY,
    settlement_date     DATE NOT NULL,
    settlement_period   SMALLINT NOT NULL,
    generation_mw       DOUBLE NOT NULL,
    source_publish_time TIMESTAMP,
    ingested_at         TIMESTAMP NOT NULL,
    run_id              VARCHAR
);
CREATE TABLE IF NOT EXISTS forecast_generation (
    target_time    TIMESTAMP NOT NULL,
    publish_time   TIMESTAMP NOT NULL,
    generation_mw  DOUBLE NOT NULL,
    ingested_at    TIMESTAMP NOT NULL,
    run_id         VARCHAR,
    PRIMARY KEY (target_time, publish_time)
);
CREATE TABLE IF NOT EXISTS snapshot_meta (
    key   VARCHAR PRIMARY KEY,
    value VARCHAR
);
"""

TS_COLS = (
    "target_time",
    "publish_time",
    "source_publish_time",
    "window_from",
    "window_to",
    "started_at",
    "finished_at",
    "ingested_at",
    "fit_window_from",
    "fit_window_to",
)


def to_naive_utc(ts: datetime | pd.Timestamp) -> datetime:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    out: datetime = t.to_pydatetime()
    return out


def _localise(df: pd.DataFrame) -> pd.DataFrame:
    for c in TS_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c]).astype("datetime64[us]").dt.tz_localize("UTC")
    return df


def frame_to_naive(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if isinstance(out[c].dtype, pd.DatetimeTZDtype):
            out[c] = out[c].dt.tz_convert("UTC").dt.tz_localize(None)
    return out


class DuckDBRepository(Repository):
    def __init__(self, path: Path | str, read_only: bool = True) -> None:
        self.path = str(path)
        self._con = duckdb.connect(self.path, read_only=read_only)
        self._lock = threading.Lock()

    # --- plumbing -------------------------------------------------------------------------
    def _query(self, sql: str, params: list[Any] | None = None) -> pd.DataFrame:
        # A cursor is an independent connection to the same database: safe per thread.
        with self._lock:
            cur = self._con.cursor()
        try:
            return _localise(cur.execute(sql, params or []).df())
        finally:
            cur.close()

    def close(self) -> None:
        self._con.close()

    # --- reads ----------------------------------------------------------------------------
    def ping(self) -> bool:
        try:
            self._query("SELECT 1")
            return True
        except duckdb.Error:
            return False

    def snapshot_info(self) -> dict[str, Any]:
        df = self._query("SELECT key, value FROM snapshot_meta")
        return dict(zip(df["key"], df["value"], strict=True))

    def actuals(self, start: datetime, end: datetime) -> pd.DataFrame:
        return self._query(
            """SELECT target_time, generation_mw, source_publish_time
               FROM actual_generation WHERE target_time >= ? AND target_time < ?
               ORDER BY target_time""",
            [to_naive_utc(start), to_naive_utc(end)],
        )

    def forecasts(
        self,
        target_start: datetime,
        target_end: datetime,
        publish_from: datetime | None = None,
        publish_to: datetime | None = None,
    ) -> pd.DataFrame:
        sql = """SELECT target_time, publish_time, generation_mw FROM forecast_generation
                 WHERE target_time >= ? AND target_time < ?"""
        params: list[Any] = [to_naive_utc(target_start), to_naive_utc(target_end)]
        if publish_from is not None:
            sql += " AND publish_time > ?"
            params.append(to_naive_utc(publish_from))
        if publish_to is not None:
            sql += " AND publish_time <= ?"
            params.append(to_naive_utc(publish_to))
        return self._query(sql + " ORDER BY target_time, publish_time", params)

    def forecast_at_horizon(self, start: datetime, end: datetime, horizon_h: float) -> pd.DataFrame:
        # ASOF JOIN == "latest vintage with publish_time <= cutoff", per target.
        return self._query(
            """WITH targets AS (
                   SELECT target_time, target_time - to_microseconds(?::BIGINT) AS cutoff
                   FROM actual_generation WHERE target_time >= ? AND target_time < ?
               )
               SELECT t.target_time, f.publish_time, f.generation_mw AS forecast_mw
               FROM targets t
               ASOF LEFT JOIN forecast_generation f
                 ON t.target_time = f.target_time AND t.cutoff >= f.publish_time
               ORDER BY t.target_time""",
            [round(horizon_h * 3_600_000_000), to_naive_utc(start), to_naive_utc(end)],
        )

    def latest_vintage_asof(
        self, target_start: datetime, target_end: datetime, cutoff: datetime
    ) -> pd.DataFrame:
        return self._query(
            """SELECT target_time, publish_time, generation_mw AS forecast_mw
               FROM forecast_generation
               WHERE target_time >= ? AND target_time < ? AND publish_time <= ?
               QUALIFY row_number() OVER (PARTITION BY target_time ORDER BY publish_time DESC) = 1
               ORDER BY target_time""",
            [to_naive_utc(target_start), to_naive_utc(target_end), to_naive_utc(cutoff)],
        )

    def horizon_matrix(self, start: datetime, end: datetime) -> pd.DataFrame:
        return self._query(
            """SELECT target_time, horizon_h, publish_time, forecast_mw
               FROM forecast_at_horizon WHERE target_time >= ? AND target_time < ?
               ORDER BY horizon_h, target_time""",
            [to_naive_utc(start), to_naive_utc(end)],
        )

    def vintage_pairs(self, start: datetime, end: datetime, max_horizon_h: float) -> pd.DataFrame:
        return self._query(
            """SELECT f.target_time, f.publish_time,
                      date_diff('second', f.publish_time, f.target_time) / 3600.0 AS horizon_h,
                      f.generation_mw AS forecast_mw, a.generation_mw AS actual_mw
               FROM forecast_generation f
               JOIN actual_generation a USING (target_time)
               WHERE f.target_time >= ? AND f.target_time < ?
                 AND f.publish_time <= f.target_time
                 AND f.publish_time >= f.target_time - to_microseconds(?::BIGINT)
               ORDER BY f.target_time, f.publish_time""",
            [to_naive_utc(start), to_naive_utc(end), round(max_horizon_h * 3_600_000_000)],
        )

    def publish_times(self, start: datetime, end: datetime) -> pd.Series:
        df = self._query(
            """SELECT DISTINCT publish_time FROM forecast_generation
               WHERE publish_time >= ? AND publish_time < ? ORDER BY publish_time""",
            [to_naive_utc(start), to_naive_utc(end)],
        )
        return df["publish_time"]

    def ingestion_runs(self) -> pd.DataFrame:
        return self._query("SELECT * FROM ingestion_run ORDER BY started_at")


class DuckDBWriter:
    """Write side, used only by the ingestion/derivation CLIs (never by the API)."""

    def __init__(self, path: Path | str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(path))
        self.con.execute(SCHEMA)

    def close(self) -> None:
        self.con.close()

    def upsert_actuals(self, df: pd.DataFrame, run_id: str, ingested_at: datetime) -> int:
        if df.empty:
            return 0
        frame = frame_to_naive(df)
        frame["ingested_at"] = to_naive_utc(ingested_at)
        frame["run_id"] = run_id
        self.con.register("incoming", frame)
        # Keep the most recently *published* value when an actual is revised.
        self.con.execute(
            """INSERT INTO actual_generation
               SELECT target_time, settlement_date, settlement_period, generation_mw,
                      source_publish_time, ingested_at, run_id FROM incoming
               ON CONFLICT (target_time) DO UPDATE SET
                   settlement_date = excluded.settlement_date,
                   settlement_period = excluded.settlement_period,
                   generation_mw = excluded.generation_mw,
                   source_publish_time = excluded.source_publish_time,
                   ingested_at = excluded.ingested_at,
                   run_id = excluded.run_id
               WHERE excluded.source_publish_time IS NULL
                  OR actual_generation.source_publish_time IS NULL
                  OR excluded.source_publish_time >= actual_generation.source_publish_time"""
        )
        self.con.unregister("incoming")
        return len(frame)

    def upsert_forecasts(self, df: pd.DataFrame, run_id: str, ingested_at: datetime) -> int:
        if df.empty:
            return 0
        frame = frame_to_naive(df)
        frame["ingested_at"] = to_naive_utc(ingested_at)
        frame["run_id"] = run_id
        self.con.register("incoming", frame)
        self.con.execute(
            """INSERT INTO forecast_generation
               SELECT target_time, publish_time, generation_mw, ingested_at, run_id FROM incoming
               ON CONFLICT (target_time, publish_time) DO UPDATE SET
                   generation_mw = excluded.generation_mw,
                   ingested_at = excluded.ingested_at,
                   run_id = excluded.run_id"""
        )
        self.con.unregister("incoming")
        return len(frame)

    def record_run(self, row: dict[str, Any]) -> None:
        r = {k: (to_naive_utc(v) if isinstance(v, datetime) else v) for k, v in row.items()}
        cols = ", ".join(r)
        marks = ", ".join("?" for _ in r)
        self.con.execute(f"INSERT INTO ingestion_run ({cols}) VALUES ({marks})", list(r.values()))

    def read(self, sql: str, params: list[Any] | None = None) -> pd.DataFrame:
        return _localise(self.con.execute(sql, params or []).df())

    def replace_table(self, name: str, df: pd.DataFrame) -> None:
        self.con.register("incoming", frame_to_naive(df))
        self.con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM incoming")
        self.con.unregister("incoming")

    def set_meta(self, items: dict[str, str]) -> None:
        for k, v in items.items():
            self.con.execute(
                "INSERT OR REPLACE INTO snapshot_meta (key, value) VALUES (?, ?)", [k, v]
            )
