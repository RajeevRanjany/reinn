"""Thin HTTP client for the Elexon Insights (BMRS) API, with chunking and retries."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any

import httpx

log = logging.getLogger(__name__)

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
RETRYABLE = {429, 500, 502, 503, 504}


class ElexonError(RuntimeError):
    pass


class ElexonClient:
    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout_s: float = 60.0,
        max_retries: int = 5,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self._client = client or httpx.Client(timeout=timeout_s)

    def _get(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.get(url, params=params)
            except httpx.TransportError as exc:
                if attempt == self.max_retries:
                    raise ElexonError(f"GET {url} failed: {exc}") from exc
                self._sleep(attempt)
                continue
            if resp.status_code in RETRYABLE and attempt < self.max_retries:
                log.warning("elexon %s -> %s, retrying", url, resp.status_code)
                self._sleep(attempt)
                continue
            if resp.status_code >= 400:
                raise ElexonError(f"GET {url} {params} -> {resp.status_code}: {resp.text[:300]}")
            body = resp.json()
            # The /stream endpoints return a bare list; the non-stream ones wrap in {"data": [...]}.
            if isinstance(body, dict):
                body = body.get("data", [])
            if not isinstance(body, list):
                raise ElexonError(f"Unexpected payload type from {url}: {type(body)}")
            return body
        raise ElexonError(f"GET {url} exhausted retries")

    @staticmethod
    def _sleep(attempt: int) -> None:
        # Exponential backoff with full jitter, capped at 30s.
        time.sleep(random.uniform(0, min(30.0, 0.5 * 2**attempt)))

    def fuelhh_wind(self, settlement_from: date, settlement_to: date) -> list[dict[str, Any]]:
        """Half-hourly outturn by fuel type, filtered to WIND. Dates are inclusive."""
        return self._get(
            "datasets/FUELHH/stream",
            {
                "settlementDateFrom": settlement_from.isoformat(),
                "settlementDateTo": settlement_to.isoformat(),
                "fuelType": "WIND",
            },
        )

    def windfor(self, publish_from: datetime, publish_to: datetime) -> list[dict[str, Any]]:
        """All WINDFOR forecast vintages published within [publish_from, publish_to]."""
        return self._get(
            "datasets/WINDFOR/stream",
            {
                "publishDateTimeFrom": _iso(publish_from),
                "publishDateTimeTo": _iso(publish_to),
            },
        )


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def day_chunks(start: date, end: date, days: int = 1) -> Iterator[tuple[date, date]]:
    """Inclusive [from, to] date chunks covering start..end."""
    cur = start
    while cur <= end:
        to = min(cur + timedelta(days=days - 1), end)
        yield cur, to
        cur = to + timedelta(days=1)
