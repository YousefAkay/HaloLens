---
description: Autopilot — pick up the next task on your track's board, build it, open a PR into dev, and stop.
---

You are working on the LeaseLens repo. Follow this routine exactly. AGENTS.md is the rulebook; this is the order of operations.

## 1. Who am I?
- Read the file `.track` at the repo root. It contains one word: INT, MSR or FCT.
- If it is missing or invalid, ask the human once which track they are, write that word to `.track`, and continue.
- Track prefixes: INT → `int/`, MSR → `msr/`, FCT → `fct/`. Your board is `docs/board/<TRACK>.md`.

## 2. Sync
- Re-read AGENTS.md (it may have changed).
- If you are on a feature branch with an open PR, that's fine: you will start the next task from dev.
- If the working tree has uncommitted changes, stop and tell the human; do not discard anything.
- Run: `git fetch origin`, `git switch dev`, `git pull`.

## 3. Find the next task
- Run `python scripts/board_status.py --track <TRACK>`. It computes every task's status from git
  (done / in-review / todo) and prints a `NEXT <TRACK>:` line. Do not edit board files to change status.
- `NEXT <TRACK>: <ID>` → do that task.
- `NEXT <TRACK> (synthetic until deps merge): <ID>` → do it against the synthetic fixtures and the contract signatures
  in `src/leaselens/contracts.py`, only if nothing you write would need to change once the dependency lands.
  Otherwise stop and report what you are waiting on. Say which case applied in the Handback Report.
- `NEXT <TRACK>: nothing workable right now` → print what you are waiting on (task IDs and owners) and stop.
- Read the task's full description and "done when" in AGENTS.md Section 10 before writing code.
- Print one line: `Picked <ID>: <task>`.

## 4. Branch
- `git switch -c <prefix><ID>-<short-name>` from dev (e.g. `msr/M-02-pairs`). The task ID must be in the branch name:
  that is how everyone's status script knows the task is in review, and later done.

## 5. (no board edits)
- Boards are static task lists. Never write status into them.

## 6. Do the task
- Do exactly the picked task as described in AGENTS.md Section 10 — nothing more, nothing from another task.
- Respect AGENTS.md: file ownership (Section 5), contracts (Section 7), no magic numbers (Section 8),
  shared decisions (Section 9), privacy (Section 3), coding standards and French Markdown in notebook sections (Section 11).
- Real-data checks print counts and aggregates only. Never print rows, unit codes or hUnit values.
- If you hit a stop condition from AGENTS.md Section 13, stop, explain the problem, the options and your recommendation.

## 7. Verify
- `python -m pytest -q` passes.
- `pre-commit run --all-files` passes.
- `git diff --name-only origin/dev` lists only files owned by your track. Fix it if not.
- Append decisions and assumptions to `docs/decisions/<TRACK>.md` and `docs/assumptions/<TRACK>.md`.

## 8. Ship
- Commit with a subject that starts with `[<TRACK>][<ID>]`, e.g. `[MSR][M-02] Add build_pairs with exclusion audit`.
- `git push -u origin <branch>`.
- If the `gh` CLI is available and authenticated: `gh pr create --base dev --title "[<TRACK>][<ID>] <summary>" --body "<Handback Report>"`.
  Otherwise print: `Open the PR: https://github.com/YousefAkay/HALO/compare/dev...<branch>?expand=1`
- Print the Handback Report (AGENTS.md Section 12) and stop. Do not start another task.

## Never
- Push to `dev` or `main`, merge anything, force-push, or use `--no-verify`.
- Edit a file your track does not own (use a change request: AGENTS.md Section 6.4).
- Send CRM rows anywhere or commit anything from `data/private/`, `outputs/private/` or `models/`.
