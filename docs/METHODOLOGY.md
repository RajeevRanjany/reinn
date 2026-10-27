# Methodology

Plain definitions of every number Headroom shows, the assumptions behind them, and what the
January 2026 data says. The design rationale is in [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md).

## 1. Data

| | Dataset | Resolution | Notes |
|---|---|---|---|
| Actual | Elexon `FUELHH`, `fuelType=WIND` | 30 min | Metered output of BM wind units. Carries a `publishTime`, used for the persistence baseline. |
| Forecast | Elexon `WINDFOR` | 60 min | 8 vintages per day (02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 UTC), each covering ~3 days ahead. |

The snapshot covers actuals for 29 Dec 2025 → 2 Feb 2026 and vintages published in the same span
(288 vintages, 21,024 forecast rows). The analysis window is **delivery days 2 Jan → 1 Feb 2026**
(1,488 half-hours, none missing). One vintage was off-schedule (15 Jan 12:25 instead of 11:30);
no publication gap exceeded 6 h.

**Resolution mismatch.** Forecasts are hourly; actuals are half-hourly. Accuracy is computed only at
target times present in both (the top of each hour, 744 per horizon). Forecasts are never
interpolated.

**Population mismatch.** `FUELHH` WIND is metered output *after* balancing actions (curtailment via
accepted bids). `WINDFOR` forecasts generation before them. Part of the persistent positive bias,
especially at high wind, is likely this definitional gap rather than forecast skill. A buyer is
exposed to the metered number, so the gap is still real risk; it just isn't all "bad forecasting".

## 2. Definitions

| Term | Definition |
|---|---|
| Delivery day D | Local (Europe/London) calendar day. Decisions made on 1–31 Jan are for D = 2 Jan → 1 Feb. |
| Horizon-h forecast for target t | Latest vintage with `publish_time ≤ t − h`. If none qualifies → missing. **Never** a later vintage. |
| Decision cutoff c(D) | Configurable local time on D−1 (default 09:00, `DECISION_CUTOFF_LOCAL`). |
| Decision forecast | For every hour of D: latest vintage with `publish_time ≤ c(D)`. With the default cutoff this is the 07:30 vintage, so horizons run ~15–38 h. |
| Error e | `forecast − actual` (MW). **Positive = over-forecast = buyer short.** |

## 3. Metrics

Bias (mean e) · MAE · RMSE · P50/P90/P99 of |e| · nMAE = MAE / mean actual · Shortfall P90 =
90th percentile of max(e, 0) · Skill = 1 − MAE / MAE(persistence) · PICP = share of actuals inside
[P10, P90] · pinball loss per quantile. MAPE is deliberately not used: it explodes at low wind.

## 4. Bands and headroom

1. Take every (target, vintage) pair with 0 ≤ horizon ≤ 48 h and a matching actual (11,873 pairs).
2. Bucket by horizon (0–6, 6–12, 12–24, 24–36, 36–48 h) and by forecast level (terciles of F:
   low < ~10 GW ≤ mid < ~16.6 GW ≤ high).
3. Per bucket, take empirical quantiles q10/q50/q90 of e. Cells with fewer than 60 samples fall
   back to the horizon-only bucket (none needed to in January).
4. Band on the actual: `[F − q90, F − q10]`, clipped to `[0, max observed actual]`.
5. Headroom per period = `max(q90, 0)`; summed over the day × 1 h it gives MWh to cover.

**Validation: leave-one-day-out.** For each delivery day, quantiles are fitted on all *other*
days and scored on that day. Decision Mode always shows these out-of-sample bands. Caveat: "other
days" include later January days, which a live desk would not have had; production should use a
trailing 90-day window.

## 5. Persistence baseline

Forecast for target t = the most recent actual whose `publishTime` ≤ cutoff (decision mode) or
≤ t − h (horizon mode). Falls back to period end + 60 min if a publish time is missing
(`ACTUAL_PUBLICATION_LAG_MIN`).

## 6. Findings (January 2026 snapshot)

| | Value |
|---|---|
| Decision-mode MAE (09:00 cutoff) | **2,022 MW**, nMAE 17.9% (mean outturn 11.3 GW) |
| Decision-mode bias | **+1,746 MW**: over-forecast in most hours |
| Decision-mode P90 shortfall | 4,154 MW |
| MAE by horizon | 1,680 MW (0 h) → 1,932 MW (24 h) → 2,301 MW (48 h) |
| Skill vs persistence | negative below 7 h (persistence wins at very short lead), **+52% at 24 h**, +51% in decision mode |
| Bias by hour (24 h ahead) | lowest 15:00 (+1,228 MW), highest 02:00 (+2,363 MW): overnight is riskiest |
| By wind level (24 h ahead) | high-wind tercile MAE 2,966 MW and almost entirely bias, consistent with curtailment |
| Band coverage, LODO, decision mode | **76.1%** vs 80% target (11.8% below P10, 12.1% above P90); in-sample 80.0% |
| Worst days | 28 Jan (0% of hours in band), 12 Jan (33%), 20 Jan (38%) |

Reading: the bands are slightly too narrow out-of-sample (expected with one month of data and
day-to-day regime changes). The fix is a longer, trailing fit window, not a different method.
