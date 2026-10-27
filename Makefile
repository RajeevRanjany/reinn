# Convenience targets (Git Bash / Linux / macOS).
PY := api/.venv/bin/python
ifeq ($(OS),Windows_NT)
PY := api/.venv/Scripts/python
endif

.PHONY: setup ingest derive api web up lint openapi

setup:
	python -m venv api/.venv && $(PY) -m pip install -r api/requirements-dev.txt
	cd web && npm ci

ingest:            ## refresh the snapshot from Elexon, then rebuild derived tables
	cd api && ../$(PY) -m ingestion.run_ingest && ../$(PY) -m ingestion.build_derived

derive:
	cd api && ../$(PY) -m ingestion.build_derived

api:
	cd api && ../$(PY) -m uvicorn app.main:app --reload --port 8000

web:
	cd web && npm run dev

up:
	docker compose up --build

lint:
	cd api && ../$(PY) -m ruff check . && ../$(PY) -m ruff format --check . && ../$(PY) -m mypy app ingestion
	cd web && npm run lint && npx tsc -b

openapi:           ## regenerate the typed TS client after an API change
	$(PY) api/scripts/export_openapi.py && cd web && npm run gen:api
