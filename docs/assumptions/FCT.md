# Assumptions FCT

Append one bullet per entry, newest last.
- F-01: Engine weights start at 0.5/0.5 with no evidence; they are only re-examined on the selection years (2023-24), never on the 2025 holdout.
- F-01: `market_anchor_series: rent_cpi` is a placeholder name; the real series id comes from MSR's `sources.csv` (M-03) and may need a rename in F-02.
- F-01: `min_pairs_per_segment: 5` and `shrinkage_strength: 20` are placeholders until real pair counts are seen (counts only).
- F-02: B2 expects released external rows with `metric == baselines.market_anchor_series`, province-code geographies (QC, ON), `ref_period_end` in the reference year and percent values. If MSR's sources.csv uses other names (for example CMA names), B2 needs a mapping in a later task or a change request.
- F-02: B1 averages yearly log headlines over the window and skips years without eligible pairs (listed in `components`).
- F-02: Pairs belong to the year of their later lease start (Section 9.2); B0 is the previous calendar year's headline with weights frozen at the cutoff.
- F-03: Leases are assigned to years by `lease_start`; a lease signed in 2024 but starting 2025 is outside the snapshot. The trend uses at most two points, so it is sensitive to one odd year; the clip and pool fallback limit the damage.
- F-03: `max_discount_share: 0.5` and `min_leases_per_cell: 5` are judgment values, to be revisited when real lease counts per segment are seen (counts only).
- F-03: The engine only converts a contractual growth forecast into a net one; it does not forecast contractual growth itself (F-05).
- F-04: The nowcast projects annualized log growth by month of lease start and assumes the calendar-month mix of recent pairs repeats next year. It does not model seasonality in growth itself.
- F-04: `trend_damping: 0.8`, `max_pool_months: 3` and `min_observed_months: 24` are untuned starting values; F-05 backtests on 2023-24 (never 2025) decide whether they stay.
