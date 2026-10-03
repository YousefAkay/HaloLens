# Decisions INT

- 2026-10-03 — Headline: fixed-composition same-unit growth in rent net of all incentives (AGENTS.md §9.1); contractual and medians as companions.
- 2026-10-03 — `sAvailable` dropped: identical to `sLeaseFrom` on every lease row (QA check).
- 2026-10-03 — Concession amounts converted to positive `credit_amount`; `PromoPay` classified as a lump credit, all other codes as monthly credits over `months`.
- 2026-10-03 — GitHub cannot enforce branch rules on the free private repo; protection via `.githooks/pre-push` plus workflow rules.
- 2026-10-03 — I-05 build: `scripts/build_notebook.py` concatenates the section files in filename order and runs them in a fresh kernel; the first failing cell fails the build (exit 1).
- 2026-10-03 — Data mode for the build comes from `core.yaml` by default, with `--synthetic` / `--real` overrides. The mode reaches the notebook through `LEASELENS_DATA_MODE` (read by `load_config` when no mode is passed).
- 2026-10-03 — Real-mode notebook is written to `outputs/private/` (gitignored, since it holds CRM aggregates); synthetic-mode notebook is written to the repo root as `project_analysis.ipynb`.
