# Decisions INT

- 2026-10-03 — Headline: fixed-composition same-unit growth in rent net of all incentives (AGENTS.md §9.1); contractual and medians as companions.
- 2026-10-03 — `sAvailable` dropped: identical to `sLeaseFrom` on every lease row (QA check).
- 2026-10-03 — Concession amounts converted to positive `credit_amount`; `PromoPay` classified as a lump credit, all other codes as monthly credits over `months`.
- 2026-10-03 — GitHub cannot enforce branch rules on the free private repo; protection via `.githooks/pre-push` plus workflow rules.
- 2026-10-03 — I-05 build: `scripts/build_notebook.py` concatenates the section files in filename order and runs them in a fresh kernel; the first failing cell fails the build (exit 1).
- 2026-10-03 — Data mode for the build comes from `core.yaml` by default, with `--synthetic` / `--real` overrides. The mode reaches the notebook through `LEASELENS_DATA_MODE` (read by `load_config` when no mode is passed).
- 2026-10-03 — Real-mode notebook is written to `outputs/private/` (gitignored, since it holds CRM aggregates); synthetic-mode notebook is written to the repo root as `project_analysis.ipynb`.
- 2026-10-03 — I-12a number guard: a number in generated text is grounded when a JSON value rounds to it at the precision the text was written with (tolerance = half a unit of the last written digit). Digit runs in JSON strings count as values; booleans never do.
- 2026-10-03 — Board: I-12a, I-13a, I-09a and I-11a added after I-06; I-11 now waits on I-09 and I-11a, I-12 on I-11a and I-12a. Section 01 is tracked as I-13a.
- 2026-10-03 — `project_analysis.ipynb` added to `.gitignore` until the I-14 submission decision.
- 2026-10-03 — `app/` made a package (`app/__init__.py`); pytest `pythonpath` now includes the repo root so tests import `app.*`.
- 2026-10-03 — I-01c: task status "done" requires a commit SUBJECT on origin/dev with the task's own track tag `[TRACK][ID]` or its branch `/prefix/ID-` (merge subject), or Notes starting "done". Commit bodies are ignored. Reason: the I-12a commit body listed other task IDs, which falsely marked I-13a, I-09a, I-11a and I-14 as done.
- 2026-10-03 — I-07 smoke run: `scripts/smoke_real_data.py` loads the tables (SHA-256 checked), builds pairs on the full history and on the snapshot at the target cutoff, and prints counts only. In real mode it refuses to run without `data/private/` and exits 2.
- 2026-10-03 — I-07: external observations are an empty table with the contract columns until the MSR registry loader (M-03) is merged; `make_snapshot` is called with it.
- 2026-10-03 — I-13a section 01: the headline definition is written in French, and every number it cites (target year, cutoff, gap bounds, quantiles, weight window, column names) is generated from config/ in a code cell, not typed into Markdown.
- 2026-10-03 — REQUEST-MSR-01 done: `pydantic>=2,<3` added to requirements.txt (MSR's request, filed in docs/requests/from_MSR.md; that file is MSR's and was not edited).
- 2026-10-03 — Board: M-03b (verify sources for 2018+ from the draft, priority after M-04) added to the MSR board after M-04. F-05 on the FCT board now depends on M-03b instead of M-03.
