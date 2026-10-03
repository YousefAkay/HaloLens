# Assumptions FCT

Append one bullet per entry, newest last.
- F-01: Engine weights start at 0.5/0.5 with no evidence; they are only re-examined on the selection years (2023-24), never on the 2025 holdout.
- F-01: `market_anchor_series: rent_cpi` is a placeholder name; the real series id comes from MSR's `sources.csv` (M-03) and may need a rename in F-02.
- F-01: `min_pairs_per_segment: 5` and `shrinkage_strength: 20` are placeholders until real pair counts are seen (counts only).
- F-02: B2 expects released external rows with `metric == baselines.market_anchor_series`, province-code geographies (QC, ON), `ref_period_end` in the reference year and percent values. If MSR's sources.csv uses other names (for example CMA names), B2 needs a mapping in a later task or a change request.
- F-02: B1 averages yearly log headlines over the window and skips years without eligible pairs (listed in `components`).
- F-02: Pairs belong to the year of their later lease start (Section 9.2); B0 is the previous calendar year's headline with weights frozen at the cutoff.
