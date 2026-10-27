# API image: FastAPI + baked January 2026 DuckDB snapshot (no Elexon dependency at runtime).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY ingestion ./ingestion
COPY data/headroom.duckdb ./data/headroom.duckdb

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
# Heroku injects $PORT; locally it defaults to 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers"]
