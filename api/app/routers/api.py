"""HTTP routes under /api/v1. Thin: validate, delegate to the service, shape the response."""

from __future__ import annotations

import io
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.deps import Cutoff, Horizon, Service, WindowDep
from app.schemas import models as M

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=M.Health, tags=["meta"])
def health(svc: Service) -> dict[str, Any]:
    ok = svc.repo.ping()
    info = svc.repo.snapshot_info() if ok else {}
    runs = svc.repo.ingestion_runs() if ok else None
    last = None
    if runs is not None and not runs.empty:
        last = runs["finished_at"].max().strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "status": "ok" if ok else "degraded",
        "db_reachable": ok,
        "data_version": svc.data_version,
        "built_at": info.get("built_at"),
        "analysis_start_utc": info.get("analysis_start_utc"),
        "analysis_end_utc": info.get("analysis_end_utc"),
        "default_cutoff_local": svc.s.decision_cutoff_local.strftime("%H:%M"),
        "delivery_dates": [d.isoformat() for d in svc.delivery_days()],
        "last_ingestion": last,
    }


@router.get("/series", response_model=M.SeriesResponse, tags=["forecast"])
def series(svc: Service, w: WindowDep, horizon_h: Horizon = 24) -> dict[str, Any]:
    return svc.series(w.start, w.end, horizon_h)


@router.get("/decision", response_model=M.DecisionResponse, tags=["forecast"])
def decision(
    svc: Service,
    cutoff: Cutoff,
    delivery_date: Annotated[date, Query(description="Delivery day D (local)")],
) -> dict[str, Any]:
    if not (svc.s.first_delivery_date <= delivery_date <= svc.s.last_delivery_date):
        raise HTTPException(
            422,
            f"delivery_date must be between {svc.s.first_delivery_date} and "
            f"{svc.s.last_delivery_date}",
        )
    return svc.decision(delivery_date, cutoff)


@router.get("/accuracy/summary", response_model=M.SummaryResponse, tags=["accuracy"])
def accuracy_summary(
    svc: Service,
    w: WindowDep,
    cutoff: Cutoff,
    horizon_h: Annotated[float | None, Query(ge=0, le=48)] = None,
    mode: Literal["horizon", "decision"] = "horizon",
) -> dict[str, Any]:
    return svc.summary(w.start, w.end, horizon_h, mode, cutoff)


@router.get("/accuracy/by-horizon", response_model=M.HorizonResponse, tags=["accuracy"])
def accuracy_by_horizon(svc: Service, w: WindowDep) -> dict[str, Any]:
    return svc.by_horizon(w.start, w.end)


@router.get("/accuracy/by-hour", response_model=M.HourResponse, tags=["accuracy"])
def accuracy_by_hour(svc: Service, w: WindowDep, horizon_h: Horizon = 24) -> dict[str, Any]:
    return svc.by_hour(w.start, w.end, horizon_h)


@router.get("/accuracy/by-level", response_model=M.LevelResponse, tags=["accuracy"])
def accuracy_by_level(svc: Service, w: WindowDep, horizon_h: Horizon = 24) -> dict[str, Any]:
    return svc.by_level(w.start, w.end, horizon_h)


@router.get("/accuracy/distribution", response_model=M.DistributionResponse, tags=["accuracy"])
def accuracy_distribution(
    svc: Service,
    w: WindowDep,
    horizon_h: Horizon = 24,
    bins: Annotated[int, Query(ge=5, le=100)] = 30,
) -> dict[str, Any]:
    return svc.distribution(w.start, w.end, horizon_h, bins)


@router.get("/accuracy/worst-misses", response_model=M.WorstMissesResponse, tags=["accuracy"])
def accuracy_worst_misses(
    svc: Service,
    w: WindowDep,
    cutoff: Cutoff,
    horizon_h: Annotated[float | None, Query(ge=0, le=48)] = None,
    mode: Literal["horizon", "decision"] = "decision",
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    return svc.worst_misses(w.start, w.end, horizon_h, mode, cutoff, limit)


@router.get("/reliability", response_model=M.ReliabilityResponse, tags=["reliability"])
def reliability(svc: Service, cutoff: Cutoff) -> dict[str, Any]:
    return svc.reliability(cutoff)


@router.get("/data-quality", response_model=M.DataQualityResponse, tags=["reliability"])
def data_quality(svc: Service, cutoff: Cutoff) -> dict[str, Any]:
    return svc.data_quality(cutoff)


@router.get("/export.csv", tags=["forecast"], response_class=StreamingResponse)
def export_csv(svc: Service, w: WindowDep, horizon_h: Horizon = 24) -> StreamingResponse:
    df = svc.series_frame(w.start, w.end, horizon_h)
    out = df[["target_time", "actual_mw", "forecast_mw", "publish_time", "error_mw"]].copy()
    out.insert(1, "horizon_h", horizon_h)
    buf = io.StringIO()
    out.to_csv(buf, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    buf.seek(0)
    name = f"headroom_h{horizon_h:g}_{w.start:%Y%m%d}_{w.end:%Y%m%d}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
