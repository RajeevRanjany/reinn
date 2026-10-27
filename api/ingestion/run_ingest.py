"""CLI: fetch FUELHH (wind) + WINDFOR from Elexon -> raw JSON landing -> DuckDB upsert.

Idempotent: re-running over the same window rewrites the same keys.

    python -m ingestion.run_ingest                      # default window from settings
    python -m ingestion.run_ingest --from 2026-01-01 --to 2026-01-03
    python -m ingestion.run_ingest --from-raw          # rebuild the DB from landed raw files
"""

from __future__ import annotations

import argparse
import json
import logging
import uuid
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.repository.duckdb_repo import DuckDBWriter
from ingestion.elexon_client import ElexonClient, day_chunks
from ingestion.normalise import Normalised, normalise_fuelhh, normalise_windfor

log = logging.getLogger("ingest")

# Over-fetch around the analysis window: 48h-ahead vintages for the first delivery day were
# published two days earlier, and the persistence baseline needs actuals before the window.
LEAD_DAYS = 4
TAIL_DAYS = 1


def _land(raw_dir: Path, dataset: str, start: date, end: date, rows: list[dict[str, Any]]) -> Path:
    folder = raw_dir / dataset.lower()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{start.isoformat()}_{end.isoformat()}.json"
    path.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
    return path


def _store(
    writer: DuckDBWriter, dataset: str, start: date, end: date, rows: list[dict[str, Any]]
) -> None:
    run_id = str(uuid.uuid4())
    started = datetime.now(UTC)
    record: dict[str, Any] = {
        "run_id": run_id,
        "dataset": dataset,
        "window_from": datetime.combine(start, time(0), tzinfo=UTC),
        "window_to": datetime.combine(end + timedelta(days=1), time(0), tzinfo=UTC),
        "started_at": started,
    }
    try:
        norm: Normalised = (
            normalise_fuelhh(rows) if dataset == "FUELHH" else normalise_windfor(rows)
        )
        upsert = writer.upsert_actuals if dataset == "FUELHH" else writer.upsert_forecasts
        n = upsert(norm.frame, run_id, started)
        status = "ok" if n > 0 else "partial"
        record |= {
            "rows_received": norm.rows_received,
            "rows_upserted": n,
            "duplicates_dropped": norm.duplicates_dropped,
            "invalid_dropped": norm.invalid_dropped,
            "status": status,
        }
        log.info(
            "%s %s..%s received=%d upserted=%d dup=%d invalid=%d",
            dataset,
            start,
            end,
            norm.rows_received,
            n,
            norm.duplicates_dropped,
            norm.invalid_dropped,
        )
    except Exception as exc:
        record |= {"status": "failed", "error": str(exc)[:500]}
        log.exception("%s %s..%s failed", dataset, start, end)
    record["finished_at"] = datetime.now(UTC)
    writer.record_run(record)


def ingest(start: date, end: date, chunk_days: int = 1) -> None:
    s = get_settings()
    client = ElexonClient()
    writer = DuckDBWriter(s.data_path)
    try:
        for a, b in day_chunks(start, end, chunk_days):
            rows = client.fuelhh_wind(a, b)
            _land(s.raw_path, "FUELHH", a, b, rows)
            _store(writer, "FUELHH", a, b, rows)

            pub_from = datetime.combine(a, time(0), tzinfo=UTC)
            pub_to = datetime.combine(b, time(23, 59, 59), tzinfo=UTC)
            rows = client.windfor(pub_from, pub_to)
            _land(s.raw_path, "WINDFOR", a, b, rows)
            _store(writer, "WINDFOR", a, b, rows)
    finally:
        writer.close()


def ingest_from_raw() -> None:
    """Rebuild the analytical store from landed raw files (no network)."""
    s = get_settings()
    writer = DuckDBWriter(s.data_path)
    try:
        for dataset in ("FUELHH", "WINDFOR"):
            for path in sorted((s.raw_path / dataset.lower()).glob("*.json")):
                a, b = (date.fromisoformat(p) for p in path.stem.split("_"))
                _store(writer, dataset, a, b, json.loads(path.read_text(encoding="utf-8")))
    finally:
        writer.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    s = get_settings()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument(
        "--from",
        dest="start",
        type=date.fromisoformat,
        default=s.first_delivery_date - timedelta(days=LEAD_DAYS),
    )
    p.add_argument(
        "--to",
        dest="end",
        type=date.fromisoformat,
        default=s.last_delivery_date + timedelta(days=TAIL_DAYS),
    )
    p.add_argument("--chunk-days", type=int, default=1)
    p.add_argument("--from-raw", action="store_true")
    args = p.parse_args()
    if args.from_raw:
        ingest_from_raw()
    else:
        ingest(args.start, args.end, args.chunk_days)


if __name__ == "__main__":
    main()
