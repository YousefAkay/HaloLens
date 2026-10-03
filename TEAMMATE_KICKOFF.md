# Teammate kickoff — LeaseLens (project  2026)

Follow these steps in order. Takes ~15 minutes. Your track: Partner 1 = **MSR** (Measure & Market), Partner 2 = **FCT** (Incentives & Forecast). Yousef = **INT** (integrator).

## 1. Accounts and access
1. Accept Yousef's GitHub invite to `YousefAkay/HALO` (private repo).
2. Get access to the **HALO** Claude project (Yousef shares it, or creates the same project on your account with these files uploaded: `project_Complete_Claude_Handoff.md`, `AGENTS.md`, `project_team_plan.md`, this file).
3. Confirm with Yousef that the sponsor approval to process CRM with Claude covers you.
4. Get the sponsor ZIP (`project-participants.zip`) from Yousef through a private channel — never via GitHub.

## 2. Local setup (terminal)
```bash
git clone https://github.com/YousefAkay/HALO.git
cd HALO
git switch dev                       # we work from dev, never main
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pre-commit install
git config core.hooksPath .githooks   # blocks accidental pushes to dev/main
mkdir -p data/private                 # unzip the 4 CSVs + template.ipynb + manifest.json here
pytest -q                             # should pass on synthetic data
```
`data/private/` is gitignored. Never move CRM files anywhere else.

## 3. Start your Claude chat (inside the HALO project)
Open a new chat in the HALO project and paste:

> I'm on the project hackathon team, track **[MSR or FCT]**. Read `AGENTS.md` and `project_team_plan.md` in this project. You'll act as my planner and reviewer: for each task in my track's list (AGENTS.md Section 10), write me one complete Claude Code prompt; I'll paste Claude Code's Handback Report back to you; you review it against AGENTS.md (ownership, contracts, privacy, definition of done) and either approve or write a fix prompt. I'm newer to Python, so explain key decisions briefly. Start with my first task.

## 4. Start Claude Code (in the repo folder)
```bash
cd HALO
claude
```
Claude Code reads `CLAUDE.md` → `AGENTS.md` automatically. First message to Claude Code each session:

> I'm working for track **[MSR/FCT]**, task **[ID]**. Confirm you've read AGENTS.md and list the files you're allowed to edit before starting.

Then paste the prompt your Claude chat wrote.

## 5. The loop (every task)
1. Claude chat → writes the prompt for task X.
2. Claude Code → does it on branch `<prefix>/<task-id>-<name>` (created from `dev`), runs tests, prints the **Handback Report**.
3. You → paste the Handback Report (and any errors) back into the Claude chat.
4. Claude chat → "approved, open the PR into **dev**" or a fix prompt. Max ~2 fix rounds.
5. You → open the PR into `dev` (never `main`). Tell Yousef. Yousef reviews and merges.
6. Before the next task: `git fetch && git switch dev && git pull`.

## 6. Rules you must not break
- Only edit files your track owns (AGENTS.md Section 5). Need something changed elsewhere? File a request in `docs/requests/from_<YOUR_TRACK>.md`.
- Never paste raw CRM rows into Claude, Claude Code output you share, PRs, or Discord/Slack. Counts and aggregates only.
- Never push to `dev` or `main` directly. PRs into `dev` only.
- Show up at sync points: H1, H4, H8 (core freeze), H11 (feature freeze), H12.5, H14.
