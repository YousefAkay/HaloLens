# Task board — MSR (Hamza)

Owner: MSR. This file only changes when the task list itself changes (via INT). Agents read it; they never edit status.
Status is NOT written here. `/next` and `/status` compute it live from git:
**done** = the task ID appears in a commit message on `origin/dev` (merge commit or PR title);
**in review** = a remote branch `<prefix><ID>-…` exists and is not done; **todo** = neither.
A row whose Notes start with `done` is done regardless (used when several tasks shipped in one PR).
Task details and "done when" criteria: AGENTS.md Section 10.

| ID | Task | Depends on | Notes |
|---|---|---|---|
| M-01 | measure.yaml keys + failing pair tests | I-01 |  |
| M-02 | build_pairs with exclusion audit (needed by FCT by H2.5) | M-01 | critical path |
| M-03 | Source registry + LLM extraction + verified sources.csv | I-01 |  |
| M-04 | Asking-rent turnover signal (needed by FCT by H6) | M-02, F-02 | uses make_snapshot; synthetic until F-02 merges |
| M-03b | Verify sources: copy rows from sources_draft.csv into sources.csv for 2018+ only (StatCan rent CPI QC/ON; CMHC same-sample growth + vacancy Montréal/Ottawa; TAL renewal reference % 2019–2026; Ontario guideline 2019–2026), each checked against its official URL, with release_date filled and verified_by set; fill gaps (TAL years, CMHC Ottawa) from official pages; list anything not found instead of guessing | M-03 | after M-04 |
| M-05 | Composition / rent bridge + sections 03, 04 | M-02 |  |
| M-06 | Renewals split + regulation matrix + section 06 | M-02, M-03 |  |
| M-07 | Internal vs market reconciliation + section 07 | M-03, M-02 |  |
| M-08 | French Markdown pass + references | M-05, M-06, M-07 |  |
| M-09 | Slides + rehearsal | M-08 |  |
