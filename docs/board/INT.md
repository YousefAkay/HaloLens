# Task board — INT (Yousef)

Owner: INT. This file only changes when the task list itself changes (via INT). Agents read it; they never edit status.
Status is NOT written here. `/next` and `/status` compute it live from git:
**done** = the task ID appears in a commit message on `origin/dev` (merge commit or PR title);
**in review** = a remote branch `<prefix><ID>-…` exists and is not done; **todo** = neither.
A row whose Notes start with `done` is done regardless (used when several tasks shipped in one PR).
Task details and "done when" criteria: AGENTS.md Section 10.

| ID | Task | Depends on | Notes |
|---|---|---|---|
| I-01 | Scaffold repo | — | done (merged in PR #2, int/I-01-scaffold) |
| I-02 | Contracts, config loader, YAML keys | — | done (merged in PR #2, int/I-01-scaffold) |
| I-03 | Synthetic fixtures + conftest | — | done (merged in PR #2, int/I-01-scaffold) |
| I-04 | Loading, data dictionary, QA, section 02 | — | done (merged in PR #2, int/I-01-scaffold) |
| I-01b | Autopilot: boards, /next, /review-pr, push guard via pre-commit | — |  |
| I-05 | build_notebook.py (sections → executed notebook) | — |  |
| I-06 | Review + merge PRs (continuous, use /review-pr) | — | continuous; never marked done |
| I-01d | /next preflight, priority marker, auto-merge of dev, requirements check | — | |
| I-01e | Windows console encoding fix for preflight | — | |
| I-01f | Explicit UTF-8 decoding for git and gh subprocess output (board status, preflight, privacy test) | — | |
| I-02b | External information date (Jan-31 rule), REQUEST-INT-01 | — | |
| I-12a | app/number_guard.py + tests/test_number_guard.py: reject generated text containing any number not present in a given aggregates JSON | — | independent of results |
| I-13a | Section 01 (notebook/sections/01_definition.py): the headline definition from AGENTS.md §9.1 in French, with its rationale, population, horizon, weighting and companions; no result numbers | — |  |
| I-09a | Define the aggregates JSON schema as AGGREGATES_SCHEMA in contracts.py (headline, companions, medians, backtest table per year and model, coverage counts, scenario range, sources, as-of date, definition text) + a synthetic example at outputs/public/aggregates_synthetic.json built from synthetic data or clearly fake values | — | lets app work start before F-05 |
| I-11a | Streamlit app shell (app/streamlit_app.py) with the four views from AGENTS.md I-11, reading only the synthetic aggregates file | I-09a |  |
| I-07 | Integration #1 smoke run on real data (counts only) | M-02, F-02 |  |
| I-08 | Unit-cluster bootstrap + section 11a | M-02, F-05 | done (moved to FCT as F-11) |
| I-09 | Aggregate export + test (no unit-level data) | F-05 |  |
| I-10 | Integration #2 / core freeze: full notebook on real data | F-05, M-05 |  |
| I-11 | Streamlit app on aggregates.json + synthetic demo | I-09, I-11a | done (merged into I-12) |
| I-12 | AI layer: scenario copilot over a precomputed scenario grid + ask-the-analysis Q&A with section citations, number guard, no-key fallbacks; app reads real aggregates.json in real mode | I-11a, I-12a |  |
| I-13 | Section 00 only (executive summary) | I-09 | section 01 done in I-13a; section 12 moved to MSR as M-10 |
| I-14 | Final build, clean kernel, fix round | all core tasks |  |
| I-15 | README, privacy check, submission, slides | I-14 |  |
