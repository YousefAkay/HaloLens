# Decisions FCT

Append one bullet per entry, newest last.
- F-01: Leakage tests are `xfail(strict, raises=NotImplementedError)` until F-02 (`make_snapshot`) and F-05 (`forecast`) land; the implementing task must remove the marker, as in M-01.
- F-01: Leakage tests run at the 2025 fold (cutoff 2024-12-31) because the synthetic data has rows after it; the cutoff day itself is inclusive.
- F-01: Snapshot `units` (listings) must be None for any cutoff before `data.data_end_date`, per AGENTS.md 9.3.
- F-01: New `forecast.yaml` keys (`snapshot`, `combine`, `leakage_test`, extra `baselines`/`incentives` keys) are starting values; each is tuned in the task that uses it.
- F-02: `make_snapshot` applies the as-of rules itself (including external `release_date <= cutoff`) instead of calling MSR's `as_of`, which is still a stub; swap in `as_of` once M-03 merges if desired. Units are kept only when every `snapshot_month` is on/before the cutoff month, so historical folds get None without needing config.
- F-02: Headline helpers (`training_pairs`, `winsor_bounds`, `frozen_weights`, `headline_summary`) live in `forecast/baselines.py` because a new shared module would need an INT request; backtest and later engines import them from there.
- F-02: `actual_for_year` winsorizes with bounds learned on pairs known at that year's cutoff, so a year more extreme than all earlier years is capped at the earlier maximum (tested). Weights of segments without pairs are dropped and the rest renormalized; `weight_coverage` is reported.
- F-02: `run_backtest` delegates to `forecast.combine.forecast` (F-05, still NotImplementedError; test is strict xfail). `backtest_baselines` runs B0-B2 through the same fold code and keeps failed baselines as NaN rows with a note.
- F-02: Removed the unused `snapshot` block from `forecast.yaml` (make_snapshot has no cfg argument).
