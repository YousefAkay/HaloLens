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
| I-07 | Integration #1 smoke run on real data (counts only) | M-02, F-02 |  |
| I-08 | Unit-cluster bootstrap + section 11a | M-02, F-05 | can start on synthetic |
| I-09 | Aggregate export + test (no unit-level data) | F-05 |  |
| I-10 | Integration #2 / core freeze: full notebook on real data | F-05, M-05 |  |
| I-11 | Streamlit app on aggregates.json + synthetic demo | I-09 |  |
| I-12 | LLM narrative + number guard + cache | I-11 |  |
| I-13 | Sections 00, 01, 12 | I-09 | 01 can start now |
| I-14 | Final build, clean kernel, fix round | all core tasks |  |
| I-15 | README, privacy check, submission, slides | I-14 |  |
