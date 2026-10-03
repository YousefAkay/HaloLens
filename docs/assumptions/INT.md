# Assumptions INT

Append one bullet per entry, newest last.
- 2026-10-03 — `project_analysis.ipynb` is a generated artifact: it is not committed in I-05. The pre-commit `nbstripout` hook would strip its outputs anyway; the submission build is run from `dev` (I-14).
- 2026-10-03 — Percentages in aggregates.json are stored in percent units (3.47), so narrative text can quote them directly; a fraction (0.0347) would be rejected by the guard.
- 2026-10-03 — The guard is strict: small counts such as "1 an" must be written as words or be present in the JSON. Intentional, to keep the narrative fully grounded.
- 2026-10-03 — Dev history cannot be rewritten, so the false "done" markers from the I-12a commit body stay in git history; they are neutralised by the subject-only rule, not by editing history.
- 2026-10-03 — Section 01 states the definition only. It shows no result numbers; the parameter table is read from config/ and is not a finding.
