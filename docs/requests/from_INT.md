# Change requests from INT

Format: AGENTS.md Section 6.4.

## REQUEST-INT-01 → FCT   status: open
File: src/leaselens/forecast/asof.py (`make_snapshot`); src/leaselens/evaluate/backtest.py (`run_backtest`, `actual_for_year`); the `forecast` wrapper in src/leaselens/forecast/combine.py; tests/test_asof_leakage.py
What: `make_snapshot(tables, external, cutoff, external_cutoff=None)`. External rows are filtered on `release_date <= external_cutoff` when it is given; the default (None) means `cutoff`, so existing calls behave as before. CRM filters stay on `cutoff`. `run_backtest` and the `estimate_2026` / `forecast` wrappers pass `config.external_cutoff_for(year, cfg)`. When `forecast_years.external_cutoff_strict_sensitivity` is true, `run_backtest` also reports the result with `external_cutoff=cutoff` (the Dec-31 version) as a sensitivity.
Why: mentor-approved 2026-10-03: public data released by January 31 of the target year may be used (TAL and December CPI are published mid-January). Contract change approved by INT.
Blocking: yes, F-05 (the headline and backtest numbers that use external data).
Workaround in place: none needed. The default `None` keeps current behaviour.
Leakage tests to add in tests/test_asof_leakage.py: (a) an external row released after `external_cutoff` is rejected; (b) a row released between `cutoff` and `external_cutoff` is accepted; (c) CRM rows after `cutoff` are still rejected; (d) with `external_cutoff=cutoff`, the snapshot equals the Dec-31 sensitivity filter.
