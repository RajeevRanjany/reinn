"""FastAPI app factory."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import Settings, get_settings
from app.repository.base import Repository
from app.repository.duckdb_repo import DuckDBRepository
from app.routers.api import router
from app.services.analytics import AnalyticsService


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        payload.update(getattr(record, "extra_fields", {}))
        return json.dumps(payload)


def _configure_logging() -> logging.Logger:
    log = logging.getLogger("headroom")
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(JsonFormatter())
        log.addHandler(h)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


def create_app(settings: Settings | None = None, repo: Repository | None = None) -> FastAPI:
    settings = settings or get_settings()
    log = _configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        r = repo or DuckDBRepository(settings.data_path, read_only=True)
        app.state.service = AnalyticsService(r, settings)
        if settings.warm_cache:
            # The leave-one-day-out refits take a few seconds; pay that at boot, not per user.
            app.state.service.reliability(settings.decision_cutoff_local)
        log.info(
            "startup", extra={"extra_fields": {"data_version": app.state.service.data_version}}
        )
        yield

    app = FastAPI(
        title="Headroom API",
        version="0.1.0",
        description="Point-in-time UK wind forecast accuracy and procurement headroom "
        "(Elexon WINDFOR vs FUELHH).",
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def access_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        response = await call_next(request)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        response.headers["x-request-id"] = rid
        log.info(
            "request",
            extra={
                "extra_fields": {
                    "request_id": rid,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "latency_ms": ms,
                }
            },
        )
        return response

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"service": "headroom-api", "docs": "/docs", "health": "/api/v1/health"}

    app.include_router(router)
    return app


app = create_app()
