"""Storage port. Business logic depends on this interface, never on a database driver.

All timestamps crossing this boundary are tz-aware UTC pandas timestamps.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import pandas as pd


class Repository(ABC):
    @abstractmethod
    def ping(self) -> bool: ...

    @abstractmethod
    def snapshot_info(self) -> dict[str, Any]:
        """Key/value metadata about the data snapshot (version, build time, windows)."""

    @abstractmethod
    def actuals(self, start: datetime, end: datetime) -> pd.DataFrame:
        """Columns: target_time, generation_mw, source_publish_time. Targets in [start, end)."""

    @abstractmethod
    def forecasts(
        self,
        target_start: datetime,
        target_end: datetime,
        publish_from: datetime | None = None,
        publish_to: datetime | None = None,
    ) -> pd.DataFrame:
        """Every vintage row. Columns: target_time, publish_time, generation_mw.

        Targets in [target_start, target_end); publish in (publish_from, publish_to].
        """

    @abstractmethod
    def forecast_at_horizon(self, start: datetime, end: datetime, horizon_h: float) -> pd.DataFrame:
        """For each *actual* target in [start, end): latest vintage with publish <= target - h.

        Columns: target_time, publish_time, forecast_mw (NaN / NaT if no vintage qualifies).
        """

    @abstractmethod
    def latest_vintage_asof(
        self, target_start: datetime, target_end: datetime, cutoff: datetime
    ) -> pd.DataFrame:
        """For each forecast target in [target_start, target_end): latest vintage with
        publish <= cutoff. Columns: target_time, publish_time, forecast_mw."""

    @abstractmethod
    def horizon_matrix(self, start: datetime, end: datetime) -> pd.DataFrame:
        """Derived target x integer-horizon matrix.

        Columns: target_time, horizon_h, publish_time, forecast_mw.
        """

    @abstractmethod
    def vintage_pairs(self, start: datetime, end: datetime, max_horizon_h: float) -> pd.DataFrame:
        """Every (target, vintage) with 0 <= horizon <= max and a matching actual.

        Columns: target_time, publish_time, horizon_h, forecast_mw, actual_mw.
        """

    @abstractmethod
    def publish_times(self, start: datetime, end: datetime) -> pd.Series:
        """Distinct vintage publish times in [start, end), sorted."""

    @abstractmethod
    def ingestion_runs(self) -> pd.DataFrame: ...
