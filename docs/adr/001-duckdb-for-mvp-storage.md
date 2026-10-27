# ADR-001: DuckDB snapshot for MVP storage

**Status:** accepted

**Context.** One month of data is ~1.7k actuals and ~21k forecast rows. The API is read-only
and must not depend on Elexon being up during review. Heroku Postgres is a paid add-on.

**Decision.** Ingest into a single DuckDB file (`api/data/headroom.duckdb`) that is baked into
the API image. DuckDB's `ASOF JOIN` maps one-to-one onto "latest vintage at or before the
cutoff". All storage access goes through `app/repository/base.py::Repository`.

**Consequences.** Zero ops, fast cold start, deterministic responses (cacheable by data
version). Multi-writer, continuous ingestion needs a `PostgresRepository` (TimescaleDB), whose
equivalent query is `DISTINCT ON (target_time) … ORDER BY target_time, publish_time DESC`. The
pure `core/` package does not change.
