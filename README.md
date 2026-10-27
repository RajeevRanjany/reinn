# Headroom: wind forecast risk desk for day-ahead power buyers

Headroom shows a GB day-ahead buying desk **exactly what the national wind forecast said at the
moment they had to commit**, how wrong forecasts like it have been at that lead time, and how many
MW of *headroom* that error implies they should plan for.

Data: Elexon BMRS `WINDFOR` (forecast) vs `FUELHH` `fuelType=WIND` (outturn), for decisions made
in January 2026 (delivery days 2 Jan → 1 Feb 2026).

| | |
|---|---|
| **Live app** | |
| **API docs** | |
| **Video** | |

## What it does

- **Decision Mode**: pick a delivery day and your cutoff (default 09:00 UK time on D−1). See the
  forecast as it stood at that moment, an out-of-sample P10–P90 band, every later vintage (how
  the forecast moved after you committed), the actual, and a **headroom MWh** figure.
- **Forecast vs Actual**: date range + 0–48 h horizon slider. For each target, the latest
  forecast published at least *h* hours before it. Metrics strip, error chart, CSV export.
- **Accuracy Explorer**: error by horizon (with a persistence baseline), by hour of day, by wind
  level, the error distribution, and the worst misses at decision time (with ramp flags).
- **Reliability & Data**: leave-one-day-out band coverage, pinball loss, skill vs persistence,
  the quantile table behind the bands, and data-quality checks (gaps, stale vintages,
  off-schedule publications).

Key findings for January 2026 are in [docs/METHODOLOGY.md](docs/METHODOLOGY.md#6-findings-january-2026-snapshot).

## Repository layout

```
.
├── README.md
├── docker-compose.yml
├── Makefile
├── .github/workflows/ci.yml
├── docs/
│   ├── SYSTEM_DESIGN.md
│   ├── METHODOLOGY.md
│   └── adr/
├── api/
│   ├── Dockerfile, heroku.yml
│   ├── requirements*.txt, pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── deps.py
│   │   ├── routers/api.py
│   │   ├── schemas/models.py
│   │   ├── services/analytics.py
│   │   ├── core/
│   │   └── repository/
│   ├── ingestion/
│   │   ├── elexon_client.py
│   │   ├── normalise.py
│   │   ├── run_ingest.py
│   │   └── build_derived.py
│   ├── scripts/export_openapi.py
│   └── data/
│       ├── headroom.duckdb
│       └── raw/
└── web/
    ├── Dockerfile, nginx.conf, vercel.json
    ├── openapi.json
    └── src/
        ├── api/
        ├── hooks/
        ├── components/
        ├── pages/
        └── lib/
```

## Run it

**Docker (one command):**

```bash
docker compose up --build
# web: http://localhost:8080   api: http://localhost:8000/docs
```

**Without Docker.** API first (from the repo root):

Windows PowerShell:

```powershell
cd api
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   
.\.venv\Scripts\Activate.ps1                                 
pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --port 8000
```

macOS / Linux / Git Bash:

```bash
cd api
python -m venv .venv
source .venv/bin/activate          # Git Bash on Windows: source .venv/Scripts/activate
pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --port 8000
```

Activation is optional: `.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000` (Windows)
or `.venv/bin/python -m uvicorn ...` works without it. Run uvicorn from the `api/` folder, or
it can't find the `app` package.

Then the web app, in a second terminal (the dev server proxies `/api` to port 8000):

```bash
cd web
npm ci
npm run dev                        # http://localhost:5173
```

**Refresh the data snapshot** (needs internet; the committed snapshot already covers January
2026):

```bash
cd api
python -m ingestion.run_ingest         
python -m ingestion.build_derived       
# or rebuild offline from landed raw files:
python -m ingestion.run_ingest --from-raw
python -m ingestion.build_derived
```

**Configuration** (env vars, all optional): `DECISION_CUTOFF_LOCAL` (default `09:00`),
`FIRST_DELIVERY_DATE` / `LAST_DELIVERY_DATE`, `BAND_MIN_SAMPLES`, `STALE_VINTAGE_HOURS`,
`CORS_ORIGINS`, `DATA_PATH`. The web app reads `VITE_API_BASE_URL` (see `web/.env.example`).

**Quality checks:** `make lint` (ruff, ruff format, mypy, ESLint, Prettier, tsc).

## API

Base path `/api/v1`. All times are ISO-8601 UTC; every response has a `meta` block (data version,
window, error sign convention). Interactive docs at `/docs`.

| Endpoint | Purpose |
|---|---|
| `GET /health` | liveness, data window, snapshot version, delivery dates |
| `GET /series?start&end&horizon_h` | actual vs horizon-h forecast per target + metrics |
| `GET /decision?delivery_date&cutoff_local` | decision forecast, P10/P50/P90, later vintages, KPIs |
| `GET /accuracy/summary?mode=horizon\|decision` | metrics block (+ skill in decision mode) |
| `GET /accuracy/by-horizon` · `/by-hour` · `/by-level` · `/distribution` | breakdowns |
| `GET /accuracy/worst-misses` | top misses + ramp vs non-ramp error |
| `GET /reliability` | leave-one-day-out coverage, pinball loss, skill, band table |
| `GET /data-quality` | missing periods, publication gaps, stale-at-cutoff days |
| `GET /export.csv` | CSV of `/series` |

## Deployment

- **Web:** Vercel, root directory `web`, build `npm run build`, output `dist`, env
  `VITE_API_BASE_URL` set to the API URL. `vercel.json` handles SPA routes.
- **API:** the `api/Dockerfile` image (FastAPI + baked DuckDB snapshot). `CORS_ORIGINS` sets the
  allowed web origins; `*.vercel.app` is also allowed by regex.

## Assumptions and limitations

- "Decisions made in January 2026" = delivery days 2 Jan → 1 Feb (decision on D−1).
- Hourly forecasts are compared only at hourly targets; nothing is interpolated.
- FUELHH (post-curtailment metered) vs WINDFOR (pre-balancing) likely explains part of the
  positive bias. Disclosed in the UI.
- One month of data makes quantiles noisy; bands under-cover slightly out-of-sample (76% vs 80%).
  Production would refit on a trailing 90-day window.
- The date-range picker sends UTC dates; in January UTC equals UK time.

