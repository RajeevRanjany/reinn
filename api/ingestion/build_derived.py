"""CLI: rebuild derived tables from the raw-normalised tables. Never edit these by hand.

    python -m ingestion.build_derived

Builds:
  forecast_at_horizon  target x integer horizon (0..48h) -> selected vintage
  error_quantiles      full-window empirical error quantiles (horizon x level buckets)
  snapshot_meta        data version, windows, resolution, cadence
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from app.config import Settings, get_settings
from app.core.bands import fit_band_model
from app.core.quality import typical_cadence_h
from app.core.selection import build_horizon_matrix
from app.repository.duckdb_repo import DuckDBWriter

log = logging.getLogger("derive")


def build(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    w = DuckDBWriter(s.data_path)
    try:
        start, end = s.analysis_start_utc, s.analysis_end_utc
        actuals = w.read(
            "SELECT target_time, generation_mw FROM actual_generation "
            "WHERE target_time >= ? AND target_time < ? ORDER BY target_time",
            [start.replace(tzinfo=None), end.replace(tzinfo=None)],
        )
        forecasts = w.read(
            "SELECT target_time, publish_time, generation_mw FROM forecast_generation"
        )

        matrix = build_horizon_matrix(forecasts, actuals["target_time"], range(s.max_horizon_h + 1))
        w.replace_table("forecast_at_horizon", matrix)
        log.info("forecast_at_horizon: %d rows", len(matrix))

        f = forecasts[(forecasts["target_time"] >= start) & (forecasts["target_time"] < end)]
        f = f.assign(horizon_h=(f["target_time"] - f["publish_time"]).dt.total_seconds() / 3600)
        f = f[(f["horizon_h"] >= 0) & (f["horizon_h"] <= s.max_horizon_h)]
        pairs = f.merge(actuals.rename(columns={"generation_mw": "actual_mw"}), on="target_time")
        pairs = pairs.rename(columns={"generation_mw": "forecast_mw"})
        model = fit_band_model(pairs, s.band_min_samples)
        table = model.table.assign(fit_window_from=start, fit_window_to=end)
        w.replace_table("error_quantiles", table)
        log.info("error_quantiles: %d cells from %d pairs", len(table), len(pairs))

        res_min = (
            forecasts.groupby("publish_time")["target_time"]
            .apply(lambda t: t.sort_values().diff().dt.total_seconds().median() / 60)
            .median()
        )
        counts = w.read(
            "SELECT (SELECT count(*) FROM actual_generation) a, "
            "(SELECT count(*) FROM forecast_generation) f, "
            "(SELECT max(ingested_at) FROM forecast_generation) i"
        ).iloc[0]
        version = hashlib.sha1(f"{counts['a']}|{counts['f']}|{counts['i']}".encode()).hexdigest()
        w.set_meta(
            {
                "data_version": version[:12],
                "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "analysis_start_utc": start.isoformat(),
                "analysis_end_utc": end.isoformat(),
                "forecast_resolution_min": str(int(res_min)),
                "actual_resolution_min": "30",
                "vintage_cadence_h": str(typical_cadence_h(forecasts["publish_time"])),
                "level_edge_low_mid": str(model.level_edges[0]),
                "level_edge_mid_high": str(model.level_edges[1]),
                "n_actuals": str(int(counts["a"])),
                "n_forecast_rows": str(int(counts["f"])),
                "n_vintages": str(forecasts["publish_time"].nunique()),
                "n_pairs": str(len(pairs)),
            }
        )
        log.info("snapshot version %s", version[:12])
    finally:
        w.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    build()


if __name__ == "__main__":
    main()
