"""Pydantic response models. These drive the OpenAPI schema and the generated TS client."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Meta(BaseModel):
    """Freshness + definitions. Endpoint-specific keys are allowed as extras."""

    model_config = ConfigDict(extra="allow")
    data_version: str
    analysis_start_utc: str | None
    analysis_end_utc: str | None
    error_sign: str
    display_timezone: str


class MetricsBlock(BaseModel):
    n: int
    n_missing: int
    bias_mw: float | None
    mae_mw: float | None
    rmse_mw: float | None
    p50_abs_mw: float | None
    p90_abs_mw: float | None
    p99_abs_mw: float | None
    nmae: float | None
    shortfall_p90_mw: float | None
    mean_actual_mw: float | None


class Health(BaseModel):
    status: str
    db_reachable: bool
    data_version: str
    built_at: str | None
    analysis_start_utc: str | None
    analysis_end_utc: str | None
    default_cutoff_local: str
    delivery_dates: list[str]
    last_ingestion: str | None


# --- /series ---------------------------------------------------------------------------
class SeriesPoint(BaseModel):
    target_time: str
    actual_mw: float | None
    forecast_mw: float | None
    publish_time: str | None
    error_mw: float | None


class SeriesResponse(BaseModel):
    meta: Meta
    metrics: MetricsBlock
    n_matched: int
    points: list[SeriesPoint]


# --- /decision -------------------------------------------------------------------------
class DecisionPoint(BaseModel):
    target_time: str
    publish_time: str | None
    horizon_h: float | None
    forecast_mw: float | None
    p10_mw: float | None
    p50_mw: float | None
    p90_mw: float | None
    headroom_mw: float | None
    horizon_bucket: str | None
    level_bucket: str | None
    actual_mw: float | None


class ActualPoint(BaseModel):
    target_time: str
    actual_mw: float | None


class VintagePoint(BaseModel):
    target_time: str
    forecast_mw: float | None


class Vintage(BaseModel):
    publish_time: str | None
    points: list[VintagePoint]


class DecisionKpis(BaseModel):
    forecast_mwh: float | None
    p10_mwh: float | None
    headroom_mwh_p90: float | None
    peak_headroom_mw: float | None
    forecast_age_at_cutoff_min: float | None
    max_revision_mw_after_cutoff: float | None
    net_revision_mw_last_vintage: float | None
    actual_mwh: float | None
    realised_shortfall_mwh: float | None
    share_in_band: float | None


class DecisionResponse(BaseModel):
    meta: Meta
    kpis: DecisionKpis
    summary: str | None
    points: list[DecisionPoint]
    actuals: list[ActualPoint]
    later_vintages: list[Vintage]


# --- /accuracy -------------------------------------------------------------------------
class SummaryResponse(BaseModel):
    meta: Meta
    metrics: MetricsBlock
    skill_vs_persistence: float | None


class HorizonRow(MetricsBlock):
    horizon_h: int
    baseline_mae_mw: float | None
    skill: float | None


class HorizonResponse(BaseModel):
    meta: Meta
    rows: list[HorizonRow]


class HourRow(MetricsBlock):
    hour: int


class HourResponse(BaseModel):
    meta: Meta
    rows: list[HourRow]


class LevelRow(MetricsBlock):
    level: str


class LevelResponse(BaseModel):
    meta: Meta
    rows: list[LevelRow]


class HistBin(BaseModel):
    lo: float
    hi: float
    count: int


class DistributionResponse(BaseModel):
    meta: Meta
    bins: list[HistBin]


class MissRow(BaseModel):
    target_time: str
    forecast_mw: float | None
    actual_mw: float | None
    error_mw: float | None
    publish_time: str | None
    horizon_h: float | None
    is_ramp: bool


class WorstMissesResponse(BaseModel):
    meta: Meta
    rows: list[MissRow]
    ramp_vs_non_ramp: dict[str, MetricsBlock]


# --- /reliability ----------------------------------------------------------------------
class BandScore(BaseModel):
    n: int
    coverage_p10_p90: float | None
    below_p10: float | None
    above_p90: float | None
    pinball_p10: float | None
    pinball_p50: float | None
    pinball_p90: float | None


class DecisionBandScore(BandScore):
    target_coverage: float


class BucketBandScore(BandScore):
    horizon_bucket: str


class DayCoverage(BaseModel):
    delivery_date: str
    n: int
    coverage: float | None


class Skill(BaseModel):
    forecast_mae_mw: float | None
    persistence_mae_mw: float | None
    skill_score: float | None
    baseline: str


class BandCell(BaseModel):
    horizon_bucket: str
    level_bucket: str
    q10: float | None
    q50: float | None
    q90: float | None
    n: int
    source: str


class ReliabilityResponse(BaseModel):
    meta: Meta
    decision: DecisionBandScore
    decision_by_day: list[DayCoverage]
    all_vintages_by_horizon_bucket: list[BucketBandScore]
    in_sample_coverage: float | None
    skill: Skill
    band_table: list[BandCell]


# --- /data-quality ---------------------------------------------------------------------
class MissingRun(BaseModel):
    start: str | None
    periods: int


class ActualsQuality(BaseModel):
    expected_periods: int
    present_periods: int
    missing: list[MissingRun]


class ForecastQuality(BaseModel):
    vintages: int
    typical_cadence_h: float | None
    gap_threshold_h: float
    publication_gaps: list[dict[str, str | float | None]]
    off_schedule_vintages: list[str | None]
    resolution_min: int


class StaleDay(BaseModel):
    delivery_date: str
    vintage_used: str | None
    age_h: float | None


class StaleBlock(BaseModel):
    threshold_h: float
    days: list[StaleDay]


class IngestionQuality(BaseModel):
    runs: int
    failed_runs: int
    duplicates_dropped: int
    invalid_rows_dropped: int


class DataQualityResponse(BaseModel):
    meta: Meta
    actuals: ActualsQuality
    forecasts: ForecastQuality
    stale_at_cutoff: StaleBlock
    ingestion: IngestionQuality
    notes: list[str]
