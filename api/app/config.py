"""Runtime configuration, read from environment variables (see README for the full list)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Storage
    data_path: Path = API_ROOT / "data" / "headroom.duckdb"
    raw_path: Path = API_ROOT / "data" / "raw"

    # Analysis window, expressed as *delivery days* (local calendar days).
    # Decisions made on 1-31 Jan 2026 are for delivery days 2 Jan -> 1 Feb 2026.
    first_delivery_date: date = date(2026, 1, 2)
    last_delivery_date: date = date(2026, 2, 1)

    # Decision cutoff: local time on D-1 at which the desk commits volume.
    decision_cutoff_local: time = time(9, 0)
    local_tz: str = "Europe/London"

    max_horizon_h: int = 48
    band_min_samples: int = 60
    stale_vintage_hours: float = 6.0
    # Assumed lag between the end of a settlement period and its outturn being known.
    # Only used when the API does not supply a publish time for an actual.
    actual_publication_lag_min: int = 60

    warm_cache: bool = True
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @field_validator("data_path", "raw_path", mode="after")
    @classmethod
    def _absolute(cls, v: Path) -> Path:
        return v if v.is_absolute() else (API_ROOT / v).resolve()

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.local_tz)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def local_day_bounds_utc(self, day: date) -> tuple[datetime, datetime]:
        """[start, end) of a local calendar day, in UTC. DST-safe (23/25h days)."""
        start = datetime.combine(day, time(0), tzinfo=self.tz)
        end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=self.tz)
        return start.astimezone(ZoneInfo("UTC")), end.astimezone(ZoneInfo("UTC"))

    @property
    def analysis_start_utc(self) -> datetime:
        return self.local_day_bounds_utc(self.first_delivery_date)[0]

    @property
    def analysis_end_utc(self) -> datetime:
        """Exclusive end of the analysis window."""
        return self.local_day_bounds_utc(self.last_delivery_date)[1]

    def decision_cutoff_utc(
        self, delivery_date: date, cutoff_local: time | None = None
    ) -> datetime:
        c = cutoff_local or self.decision_cutoff_local
        local = datetime.combine(delivery_date - timedelta(days=1), c, tzinfo=self.tz)
        return local.astimezone(ZoneInfo("UTC"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
