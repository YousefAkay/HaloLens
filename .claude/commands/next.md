---
description: Autopilot — pick up the next task on your track's board, build it, open a PR into dev, and stop.
---

You are working on the Halo Lens repo. Follow this routine exactly. AGENTS.md is the rulebook; this is the order of operations.

## 0. Preflight
- From the repo root, run the project venv interpreter on `scripts/preflight.py`:
  `.venv\Scripts\python.exe scripts/preflight.py` (Windows) or `.venv/bin/python scripts/preflight.py` (macOS / Linux).
- Exit code 0: print its one-line `PREFLIGHT: ok …` summary and go on to step 1.
- Exit code 1: stop. Print every `STOP [...]` line exactly as the script wrote it. Each line gives the fix. Do not work around it.
- `WARN [gh] …` lines do not stop the run. Print them once.
- If the script prints `**⚠️ REQUIREMENTS.TXT CHANGED — RUN pip install -r requirements.txt NOW**`, it has already run
  the install and written `.last_install`. Check that it reported success; if it did not, that is a stop.
- Never open or print the contents of any `.env` file, and never print sponsor rows.

## 1. Who am I?
- Read the file `.track` at the repo root. It contains one word: INT, MSR or FCT.
- If it is missing or invalid, ask the human once which track they are, write that word to `.track`, and continue.
- Track prefixes: INT → `int/`, MSR → `msr/`, FCT → `fct/`. Your board is `docs/board/<TRACK>.md`.

## 2. Sync
- Re-read AGENTS.md (it may have changed).
- Preflight (step 0) already switches a clean tree to dev and pulls origin/dev. It stops only for uncommitted changes,
  or for local dev commits that origin/dev does not have. Those stops name the fix; do not work around them.
- Run: `git fetch origin`, `git switch dev`, `git pull`.

## 3. Find the next task
- Run `python scripts/board_status.py --track <TRACK>`. It computes every task's status from git
  (done / in-review / todo) and prints a `NEXT <TRACK>:` line. Do not edit board files to change status.
  A workable row whose Notes start with "priority" is picked before the other workable rows; board order breaks ties.
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
- Before pushing: `git fetch origin && git merge origin/dev` on the task branch. Conflicts in `docs/decisions/*.md`,
  `docs/assumptions/*.md` and `docs/references/*.md` are append-only: keep both sides, dev's lines first (the
  `merge=union` rule in `.gitattributes` does the same automatically). Any other conflict: stop and tell the human.
  Then run the tests again.
- `git push -u origin <branch>`.
- If the `gh` CLI is available and authenticated: `gh pr create --base dev --title "[<TRACK>][<ID>] <summary>" --body "<Handback Report>"`.
  Otherwise print: `Open the PR: https://github.com/YousefAkay/HALO/compare/dev...<branch>?expand=1`
- Print the Handback Report (AGENTS.md Section 12) and stop. Do not start another task.

## Never
- Push to `dev` or `main`, merge anything, force-push, or use `--no-verify`.
- Edit a file your track does not own (use a change request: AGENTS.md Section 6.4).
- Send CRM rows anywhere or commit anything from `data/private/`, `outputs/private/` or `models/`.
