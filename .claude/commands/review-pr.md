---
description: (INT) Pre-merge check of a teammate's PR. Argument: PR number or branch name.
argument-hint: <PR number or branch>
---

Review `$ARGUMENTS` before Yousef merges it. Do not merge, push or edit anything.

1. Identify the branch (if a PR number is given and `gh` is available: `gh pr view $ARGUMENTS --json headRefName,baseRefName,body`).
   Confirm the base branch is `dev`. Fetch and check it out in a temporary worktree or detached HEAD.
2. Ownership: list `git diff --name-only origin/dev...<branch>`. Every file must be owned by the track in the branch prefix (AGENTS.md Section 5). Board edits only on that track's own board.
3. Tests: `python -m pytest -q` on the branch. `pre-commit run --all-files`.
4. Privacy scan of the diff: CSV files outside data/public and data/synthetic, anything under data/private, outputs/private or models, notebooks with outputs, `.env`, printed rows or unit identifiers in notebook sections.
5. Rules scan: numeric thresholds or dates hardcoded instead of read from config; use of `sSite` as a key; functions that don't match `contracts.py` signatures; data-changing notebook steps without a French Markdown cell before them.
6. Handback Report present in the PR body (if visible) and consistent with the diff.
7. Return to the branch you started on.

Output:
- **Verdict: MERGE** or **Verdict: FIX**
- If FIX: a numbered list of exact fixes the author's agent should make (file, problem, fix). Keep it short enough to paste into their chat.
