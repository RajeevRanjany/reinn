"""Request dependencies: the service singleton and shared query-parameter validation."""

from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request

from app.services.analytics import AnalyticsService


def get_service(request: Request) -> AnalyticsService:
    svc: AnalyticsService = request.app.state.service
    return svc


Service = Annotated[AnalyticsService, Depends(get_service)]


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


class Window:
    def __init__(self, start: datetime, end: datetime) -> None:
        self.start = start
        self.end = end


def window(
    svc: Service,
    start: Annotated[datetime | None, Query(description="ISO-8601; naive = UTC")] = None,
    end: Annotated[datetime | None, Query(description="ISO-8601, exclusive; naive = UTC")] = None,
) -> Window:
    s, e = _utc(start), _utc(end)
    if s is not None and e is not None and s >= e:
        raise HTTPException(422, "start must be before end")
    st, en = svc.clamp(s, e)
    if st >= en:
        raise HTTPException(
            422,
            f"Requested range is outside the data window "
            f"{svc.s.analysis_start_utc.isoformat()} .. {svc.s.analysis_end_utc.isoformat()}",
        )
    return Window(st, en)


WindowDep = Annotated[Window, Depends(window)]

Horizon = Annotated[float, Query(ge=0, le=48, description="Forecast horizon in hours (0-48)")]


def parse_cutoff(
    svc: Service,
    cutoff_local: Annotated[
        str | None,
        Query(pattern=r"^([01]\d|2[0-3]):[0-5]\d$", description="HH:MM local time on D-1"),
    ] = None,
) -> time:
    if cutoff_local is None:
        return svc.s.decision_cutoff_local
    hh, mm = cutoff_local.split(":")
    return time(int(hh), int(mm))


Cutoff = Annotated[time, Depends(parse_cutoff)]
