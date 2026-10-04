# Change requests from FCT

Format: AGENTS.md Section 6.4.

## REQUEST-FCT-01 → MSR   status: done (0b4d0fa)
File: src/leaselens/market/asking.py
What: `turnover_signal` (via `matched_spreads`, line ~70) raises `TypeError: float() argument must be ... 'NaTType'` when `snapshot.asking` has no rows. Return the usual SIGNAL_COLUMNS table with `expected_loggrowth_contract` NaN and `signal_source` "none" instead.
Why: a snapshot cut before any asking history (or a hand-made test snapshot) should give "no signal", not a crash.
Blocking: no
Workaround in place: none any more (the guard in src/leaselens/forecast/combine.py was removed once MSR's fix merged)
