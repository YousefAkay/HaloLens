# Task board — FCT (Yousif)

Owner: FCT. This file only changes when the task list itself changes (via INT). Agents read it; they never edit status.
Status is NOT written here. `/next` and `/status` compute it live from git:
**done** = the task ID appears in a commit message on `origin/dev` (merge commit or PR title);
**in review** = a remote branch `<prefix><ID>-…` exists and is not done; **todo** = neither.
A row whose Notes start with `done` is done regardless (used when several tasks shipped in one PR).
Task details and "done when" criteria: AGENTS.md Section 10.

| ID | Task | Depends on | Notes |
|---|---|---|---|
| F-01 | forecast.yaml keys + leakage tests first | I-01 |  |
| F-02 | make_snapshot, baselines, metrics, backtest skeleton | F-01 |  |
| F-03 | Incentive engine (discount trend per segment) | F-02 |  |
| F-04 | Monthly index + nowcast | M-02, F-02 | synthetic until M-02 merges |
| F-05 | Combine engines + backtests 2023–25 (core freeze) | F-03, F-04, M-03b, M-04 | critical path |
| F-05b | Use Jan-31 information date for public data (REQUEST-INT-01) | F-05, I-02b | |
| F-06 | Concession→lease reconciliation matcher + section 05 | F-02 |  |
| F-07 | Champion selection, scenarios, per building × beds, model | F-05 |  |
| F-08 | Sections 08, 09, 10, 11b | F-05 |  |
| F-09 | Slides + rehearsal | F-08 |  |
