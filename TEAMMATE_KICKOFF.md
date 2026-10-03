# Teammate kickoff — LeaseLens (project  2026)

Follow these steps in order. Takes ~15 minutes. Your track: Hamza = **MSR** (Measure & Market), Yousif = **FCT** (Incentives & Forecast). Yousef = **INT** (integrator).

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
git config --unset-all core.hooksPath   # only matters if you set it earlier; ignore errors
pre-commit install                       # installs commit checks + the push guard for dev/main
mkdir -p data/private                 # unzip the 4 CSVs + template.ipynb + manifest.json here
pytest -q                             # should pass on synthetic data
```
`data/private/` is gitignored. Never move CRM files anywhere else.

## 3. Tell the repo who you are (once)
In the HALO folder, create the file `.track` containing only your track code:
```powershell
Set-Content .track MSR      # Hamza
Set-Content .track FCT      # Yousif
```
It's gitignored, so it never leaves your machine.

## 4. Work loop: `/next`
```bash
claude
```
Then type:
```
/next
```
Claude Code reads `AGENTS.md`, works out your next task from your board and git history, builds it on a new branch, runs the tests, pushes the branch, opens a PR into `dev` (or prints the link), prints a Handback Report and stops.

You then:
1. Open the PR if it only printed a link (base must be **dev**).
2. Tell Yousef it's ready. He reviews and merges.
3. Type `/next` again right away. If your next task depends on the PR you just opened, the agent picks another task or tells you it's waiting.

Other commands: `/status` shows all three boards at a glance.

## 5. When to use your Claude chat (HALO project)
Only when the agent stops and asks for a decision, when tests fail and you're stuck, or at the sync points (H4, H8, H11). Paste the Handback Report or the error there.

## 6. Rules you must not break
- Only edit files your track owns (AGENTS.md Section 5). Need something changed elsewhere? File a request in `docs/requests/from_<YOUR_TRACK>.md`.
- Never paste raw CRM rows into Claude, Claude Code output you share, PRs, or Discord/Slack. Counts and aggregates only.
- Never push to `dev` or `main` directly. PRs into `dev` only.
- Show up at sync points: H1, H4, H8 (core freeze), H11 (feature freeze), H12.5, H14.
