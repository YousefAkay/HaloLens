# Decisions FCT

Append one bullet per entry, newest last.
- F-01: Leakage tests are `xfail(strict, raises=NotImplementedError)` until F-02 (`make_snapshot`) and F-05 (`forecast`) land; the implementing task must remove the marker, as in M-01.
- F-01: Leakage tests run at the 2025 fold (cutoff 2024-12-31) because the synthetic data has rows after it; the cutoff day itself is inclusive.
- F-01: Snapshot `units` (listings) must be None for any cutoff before `data.data_end_date`, per AGENTS.md 9.3.
- F-01: New `forecast.yaml` keys (`snapshot`, `combine`, `leakage_test`, extra `baselines`/`incentives` keys) are starting values; each is tuned in the task that uses it.
