# Change requests from FCT

Format: AGENTS.md Section 6.4.

## REQUEST-FCT-01 → MSR   status: done (0b4d0fa)
File: src/leaselens/market/asking.py
What: `turnover_signal` (via `matched_spreads`, line ~70) raises `TypeError: float() argument must be ... 'NaTType'` when `snapshot.asking` has no rows. Return the usual SIGNAL_COLUMNS table with `expected_loggrowth_contract` NaN and `signal_source` "none" instead.
Why: a snapshot cut before any asking history (or a hand-made test snapshot) should give "no signal", not a crash.
Blocking: no
Workaround in place: none any more (the guard in src/leaselens/forecast/combine.py was removed once MSR's fix merged)

## REQUEST-FCT-02 → INT   status: open
File: requirements.txt
What: raise the lower bound of `streamlit` (now `>=1.38,<2`) to the version the app was tested on (1.65), or confirm a lower minimum by running tests/test_app_shell.py and tests/test_app_charts.py on it. The app uses `st.tabs(default=...)`, `st.altair_chart(width="stretch")` and `st.container(key=...)`; I could not confirm from the release notes that all three exist in 1.38, and I only tested on 1.65.0.
Why: a fresh `pip install -r requirements.txt` resolves to the newest 1.x and works, but an older pinned environment inside the declared range could crash at the tabs.
Blocking: no
Workaround in place: none
