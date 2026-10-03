# AGENTS.md — LeaseLens (project  2026, the portfolio)

This file is the single source of truth for every AI coding agent (Claude Code) and every human on this repo.
Read it fully at the start of every session. If anything you are asked to do conflicts with this file, STOP and say so.

---

## 0. TL;DR for agents (read this even if you read nothing else)

1. Find out **which track you are working for** (INT, MSR or FCT). The human will tell you. If they don't, ask before touching anything.
2. You may **only create or edit files owned by your track** (Section 5). No exceptions. If you need a change in someone else's file, write a change request (Section 6.4) and stop.
3. **Never** commit, print, paste, or send CRM rows. CRM CSVs live only in `data/private/` (gitignored). Outputs that show rows never leave the machine (Section 3).
4. Every function you write must match the **contracts** in `src/leaselens/contracts.py` (Section 7). Never change contracts yourself; only INT can.
5. **No magic numbers.** Every threshold, date, window or weight lives in your track's YAML under `config/` (Section 8).
6. Work only on the task ID you were given (Section 10). Don't "also fix" other things. Don't start the next task.
7. End every task with the **Handback Report** (Section 12), exactly in that format.
8. Code and identifiers in **English**. Notebook Markdown in **French**. Commit messages in English.

---

## 1. The challenge (what we are building)

Estimate the **2026 rent increase** of the portfolio (6 buildings: Building, Building, Building in Laval; Building in Mont-Royal; Building in Pointe-Claire; the Ontario new-build in Ottawa) from lease history ending December 2025 plus public market data. Name and defend the definition. Validate by backtest on 2023, 2024 and 2025.

Graded deliverable: a Jupyter notebook derived from the sponsor's `template.ipynb`, with `estimate_2026()` and `backtest()` implemented. Also: README, saved model (if any), final % with its definition, jury presentation. Optional dashboard.

### Rubric (100 pts) and who carries it

| Criterion | Pts | Main owner |
|---|---:|---|
| Definition of the increase | 10 | INT (agreed by all at H0) |
| Data analysis & composition effects | 15 | INT (dictionary/QA) + MSR (composition) |
| Same-unit lease matching | 15 | MSR |
| Concessions | 10 | FCT |
| Renewals vs turnovers (QC vs ON rules) | 10 | MSR |
| External data | 15 | MSR |
| Forecast & backtest | 15 | FCT |
| Notebook quality | 10 | INT (assembly) + everyone (their sections) |

Point losses the sponsor names explicitly: magic numbers, badly named or inconsistent variables, matching on `sSite + sUnitCode`, misuse of variables/features, missing Markdown, quoting occupancy/vacancy/absorption from this extract.

### Sponsor rules (non-negotiable)
- Python + Jupyter, starting from `template.ipynb`. Credit the starter for what we reuse.
- Source files stay byte-for-byte unchanged. All renaming/transforming happens in our code.
- CRM data: no publication, no GitHub (not even private), no Kaggle, not in deliverables.
- Cite public data, articles and AI tools used (Claude Code, Claude, LLM API) in the References section.
- A Markdown cell at every step that changes data (not after every line).
- Match units on `sPropCode + sUnitCode` (or `hUnit`). **Never `sSite + sUnitCode`.**
- Distinguish renewals from turnovers (`sRenewal`). Never apply one province's cap to the other: 5 buildings under Québec's TAL, the Ontario new-build under Ontario.
- This extract cannot measure occupancy, vacancy, absorption or total rent roll. Never compute or quote them.

---

## 2. Team and tracks

| Code | Track | Person | Branch prefix | Summary |
|---|---|---|---|---|
| **INT** | Integration & Product | Yousef (integrator) | `int/` | Repo, contracts, config, loading/QA/dictionary, notebook assembly, uncertainty (bootstrap), aggregate export, Streamlit app + LLM narrative, README, final checks |
| **MSR** | Measure & Market | Hamza | `msr/` | Same-unit matching, composition/rent bridge, renewals vs turnovers, QC/ON regulation, external sources + LLM extraction, asking-rent turnover signal, internal vs market reconciliation |
| **FCT** | Incentives & Forecast | Yousif | `fct/` | As-of snapshot + leakage tests, baselines, incentive engine, monthly index + nowcast, engine combination, backtests, scenarios, concession→lease reconciliation matcher, `estimate_2026()` / `backtest()` |

Effort is balanced at ~13 h each including INT's integration duties. Integrator duties count as INT's work.

The integrator (INT) is the only person who merges PRs into `dev`, the only person who merges `dev` into `main`, the only owner of shared files, and the tie-breaker on conflicts.

---

## 3. Privacy and data handling (read twice)

Approval on record: the sponsor/mentor approved Claude processing the CRM CSVs for this analysis (2026-10-03). Every teammate confirms the approval covers their own Claude Code session before running anything on real data. Publication rules are unchanged.

### 3.1 Where data lives
- `data/private/` — original CRM CSVs + `template.ipynb` + `instructions.pdf`. **Gitignored. Read-only.** Each teammate copies the files there locally from the sponsor ZIP. Never moved, renamed or edited.
- `data/synthetic/` — fully invented fixtures generated by `scripts/make_synthetic.py`. Safe to commit.
- `data/public/` — public-source extracts (CMHC, StatCan, TAL, Ontario). Safe to commit.
- `outputs/private/` — anything computed from real CRM data (tables, charts, pair audits). **Gitignored.**
- `outputs/public/` — only synthetic outputs, or aggregates the sponsor approved. INT decides what goes here.
- `models/` — trained artifacts. **Gitignored** until sponsor guidance.

### 3.2 Hard rules for agents
- Never `print(df)`, `df.head()`, `df.sample()` or display raw rows of CRM tables in the terminal, notebook, logs, tests or Handback Reports. Show **counts, shapes, column names, dtypes, aggregates** only.
- In notebook sections: aggregates only (group-bys with counts, medians, rates). No row-level tables, no unit codes, no `hUnit` values, no addresses.
- Never send CRM rows or row-level derived data to any external API (LLM, web, telemetry). The LLM API only ever receives **public pages** (MSR extraction) or **aggregate JSON** (INT narrative).
- Never commit: `*.csv` outside `data/public/` and `data/synthetic/`, any `.ipynb` with outputs, `.env`, anything in `data/private/`, `outputs/private/`, `models/`.
- Tests run on **synthetic fixtures**. A real-data check is a separate, clearly named script or notebook cell that prints counts only.
- If you notice CRM data about to be committed or sent somewhere, stop immediately and tell the human.

### 3.3 Secrets
- LLM API key goes in `.env` (gitignored) as `ANTHROPIC_API_KEY`. `.env.example` (committed) has the variable name with no value.
- Load with `python-dotenv`. Never hardcode, print or log a key.
- Every feature that uses the API must work without it (cached fallback).

---

## 4. Repository layout

```
HALO/
├─ AGENTS.md                      # this file (INT)
├─ CLAUDE.md                      # points Claude Code to AGENTS.md (INT)
├─ TEAMMATE_KICKOFF.md            # onboarding steps for partners (INT)
├─ README.md                      # run instructions, versions, sources, AI tools (INT)
├─ requirements.txt               # pinned versions (INT)
├─ pyproject.toml                 # package config for src/leaselens, pytest config (INT)
├─ .gitignore  .gitattributes  .env.example  .pre-commit-config.yaml      (INT)
├─ .githooks/guard_push.py        # pre-push guard run by pre-commit: blocks pushes to main/dev (INT)
├─ .claude/commands/  next.md  review-pr.md  status.md   # slash commands (INT)
├─ .claude/settings.json          # Claude Code permissions for this repo (INT)
├─ .track                         # local only, gitignored: INT, MSR or FCT
├─ project_analysis.ipynb           # GENERATED by scripts/build_notebook.py — never hand-edited (INT)
├─ config/
│  ├─ core.yaml                   # paths, cutoff dates, target years, headline definition, seeds (INT)
│  ├─ measure.yaml                # gap bounds, winsor quantiles, composition strata, regulation refs (MSR)
│  └─ forecast.yaml               # windows, engine weights, nowcast params, scenario levers (FCT)
├─ src/leaselens/
│  ├─ __init__.py  contracts.py  config.py                (INT)
│  ├─ io/        load.py  dictionary.py  qa.py            (INT)
│  ├─ measure/   pairs.py  composition.py  renewals.py    (MSR)
│  ├─ market/    registry.py  asking.py  regulation.py  reconcile_market.py   (MSR)
│  ├─ incentives/ engine.py  linking.py  reconcile.py     (FCT)
│  ├─ forecast/  asof.py  baselines.py  monthly_index.py  nowcast.py  combine.py  scenarios.py  (FCT)
│  ├─ evaluate/  backtest.py  metrics.py (FCT)   uncertainty.py (INT)
│  └─ export/    aggregates.py                            (INT)
├─ notebook/sections/             # jupytext "percent" .py files, assembled in numeric order
│  ├─ 00_executive.py  01_definition.py  02_data_dictionary_qa.py      (INT)
│  ├─ 03_composition.py  04_matching.py  06_renewals_regulation.py  07_external.py  (MSR)
│  ├─ 05_concessions.py  08_forecast_method.py  09_backtest.py  10_forecast_2026.py  11b_scenarios.py  (FCT)
│  ├─ 11a_uncertainty.py  12_references.py               (INT)
├─ scripts/
│  ├─ build_notebook.py  make_synthetic.py  export_aggregates.py  board_status.py   (INT)
│  └─ extract_sources.py                                  (MSR)
├─ app/  streamlit_app.py  narrative.py  number_guard.py  cache/      (INT)
├─ data/  private/ (gitignored)  synthetic/ (INT)  public/sources.csv + sources_draft.csv (MSR)
├─ outputs/  private/ (gitignored)  public/ (INT)
├─ models/  (gitignored; FCT writes, nobody commits)
├─ tests/
│  ├─ conftest.py  test_contracts.py  test_io.py  test_privacy_guard.py  test_build_notebook.py  test_uncertainty.py  test_number_guard.py  (INT)
│  ├─ test_pairs.py  test_composition.py  test_registry.py  test_asking.py  test_regulation.py           (MSR)
│  └─ test_asof_leakage.py  test_baselines.py  test_incentives.py  test_linking.py  test_backtest.py  test_combine.py  (FCT)
└─ docs/
   ├─ rubric_checklist.md                                 (INT)
   ├─ decisions/INT.md  decisions/MSR.md  decisions/FCT.md
   ├─ assumptions/INT.md  assumptions/MSR.md  assumptions/FCT.md
   ├─ references/INT.md  references/MSR.md  references/FCT.md
   ├─ requests/from_INT.md  requests/from_MSR.md  requests/from_FCT.md
   └─ board/INT.md  board/MSR.md  board/FCT.md      # static task lists; status computed by scripts/board_status.py
```
Each `docs/*/XXX.md` file is owned by the track in its name.

---

## 5. File ownership (the rule that prevents collisions)

**Every file has exactly one owner track. Only that track's agent may create, edit, rename or delete it.**

| Owner | Files |
|---|---|
| INT | `AGENTS.md`, `CLAUDE.md`, `TEAMMATE_KICKOFF.md`, `.githooks/*`, `.claude/*`, `docs/board/*` (task lists change only through INT), `scripts/board_status.py`, `README.md`, `requirements.txt`, `pyproject.toml`, `.gitignore`, `.gitattributes`, `.env.example`, `.pre-commit-config.yaml`, `project_analysis.ipynb`, `config/core.yaml`, `src/leaselens/__init__.py`, `contracts.py`, `config.py`, `io/*`, `evaluate/uncertainty.py`, `export/*`, sections `00`, `01`, `02`, `11a`, `12`, `scripts/build_notebook.py`, `scripts/make_synthetic.py`, `scripts/export_aggregates.py`, `app/*`, `data/synthetic/*`, `outputs/public/*`, tests listed as INT above, `docs/rubric_checklist.md`, `docs/*/INT.md`, every `__init__.py` |
| MSR | `config/measure.yaml`, `measure/*`, `market/*`, sections `03`, `04`, `06`, `07`, `scripts/extract_sources.py`, `data/public/*`, tests listed as MSR above, `docs/*/MSR.md` |
| FCT | `config/forecast.yaml`, `incentives/*`, `forecast/*`, `evaluate/backtest.py`, `evaluate/metrics.py`, sections `05`, `08`, `09`, `10`, `11b`, `models/*` (local only), tests listed as FCT above, `docs/*/FCT.md` |

Rules:
- A new file must go inside a folder your track owns, and you add it to this table via a request to INT in the same task.
- You may **import** anything from anyone. You may never **edit** what you import.
- If you find a bug in another track's file: do not fix it. Write a change request and, if blocking, a minimal workaround **inside your own file** with a `# TODO(REQUEST-xx)` comment.
- `__init__.py` files are INT's. Ask INT to export new public functions.
- `requirements.txt` is INT's. Need a package? Change request with name + reason. Prefer what's already installed.

---

## 6. Git workflow

### 6.1 Branches
```
main   ← final, submission-ready only. INT merges dev → main at the end (and optionally at the H8 core freeze). Nobody else touches it.
 └─ dev   ← integration branch. Every PR targets dev. Nobody pushes to dev directly, not even INT; only merged PRs land here.
     ├─ int/I-04-dictionary
     ├─ msr/M-02-pairs
     └─ fct/F-02-baselines
```
- `main` and `dev` are both protected: no direct pushes, no force-pushes, ever. GitHub can't enforce rulesets on this private repo (free plan), so protection is enforced by a pre-push hook (`.githooks/guard_push.py`, installed by `pre-commit install`), by `.claude/settings.json` deny rules, and by these rules. Agents must never bypass hooks (`--no-verify` is forbidden).
- Always branch **from `dev`**: `git fetch && git switch -c msr/M-02-pairs origin/dev`.
- Feature branches: `<prefix>/<task-id>-<short-name>`, e.g. `msr/M-02-pairs`, `fct/F-04-nowcast`, `int/I-03-dictionary`.
- One task = one branch = one PR **into `dev`**. Keep PRs small (ideally < 400 changed lines).
- Agents never open a PR into `main` and never merge anything. Merging is INT's (human) job.
- Release to `main`: INT opens a PR `dev → main` titled `[RELEASE] <milestone>` after the notebook builds cleanly from `dev`; tag it (`v-core-freeze`, `v-submission`).

### 6.2 Before opening a PR
1. `git fetch && git rebase origin/dev` (resolve conflicts only inside your own files; if a conflict touches another track's file, stop and tell INT).
2. `pre-commit run --all-files` passes.
3. `pytest -q` passes (synthetic fixtures).
4. `git diff --name-only origin/dev` lists **only files your track owns**. If not, fix it before pushing.
5. Open the PR with base branch **`dev`** (never `main`). Title: `[<TRACK>][<task-id>] <summary>`. Body: paste the Handback Report.

### 6.3 Commits
- Subject starts with `[<TRACK>][<task-id>]`, then an imperative English message: `[MSR][M-02] Add exclusion audit to build_pairs`. The task ID is required: `scripts/board_status.py` uses it to mark tasks done.
- Never commit generated outputs, data, models or `.env`.

### 6.4 Change requests (the only way to affect another track's file)
Append to `docs/requests/from_<YOUR_TRACK>.md`:
```
## REQUEST-<TRACK>-<nn> → <TARGET TRACK>   status: open
File: <path>
What: <exact change: new column / new function / signature change / package>
Why: <what it unblocks>
Blocking: yes/no (if yes, which task)
Workaround in place: <file + TODO marker, or none>
```
The target track handles it in their next task and marks it `done (<commit>)`. Contract changes go to INT only.

---

## 7. Contracts (shared interfaces)

`src/leaselens/contracts.py` is the shared language. It defines canonical column names, table schemas (as column lists + dtypes) and dataclasses. INT writes it at H0–H1; it is **frozen after H1**. Any change after that needs a change request to INT and is announced to all.

### 7.1 Canonical names (data dictionary v2)
Original source names are kept in a mapping (`dictionary.py`) shown in notebook section 02.

**Leases** (`lease_history.csv` → `LEASES`):
| canonical | source | notes |
|---|---|---|
| `unit_id` | `hUnit` | str; join key |
| `prop_code`, `unit_code` | `sPropCode`, `sUnitCode` | str; unit_code keeps leading zeros |
| `building`, `province`, `city` | `sBuilding`, `sState`, `sCity` | province ∈ {`QC`,`ON`} |
| `beds`, `baths`, `sqft`, `floor`, `unit_type` | `sBeds`, `sBaths`, `sSqft`, `sFloor`, `sUnitType` | attributes as recorded on the lease row |
| `lease_seq` | `sTermSeq` | int |
| `is_renewal` | `sRenewal` | bool |
| `sign_date`, `lease_start`, `lease_end` | `sSignDate`, `sLeaseFrom`, `sLeaseTo` | datetime; lease_end is contractual, not move-out |
| `term_months_daycount` | `sTermMonths` | day-count artefact values (e.g. 17.9) |
| `term_label` | `sLeaseTerm` | label only, not a duration |
| `rent_contract` | `sRent` | monthly contractual rent |
| `rent_net_all_incentives` | `sRentEffective` | monthly rent net of ALL concession codes incl. accessories |
| `has_concession` | `sConcession` | bool flag (== rent_net_all_incentives < rent_contract) |
| *(dropped)* | `sAvailable` | identical to `sLeaseFrom` on every row; documented and dropped |

**Concessions** (`CONCESSIONS`): `concession_id` (row index), `unit_id`, `prop_code`, `unit_code`, `charge_code`, `charge_desc`, `credit_amount` (= −`sAmount`, positive), `date_from`, `date_to`, `months`, `credit_kind` ∈ {`lump`,`monthly`} (`PromoPay` = lump; all others = monthly per `months`).

**Asking** (`ASKING`): `unit_id`, `prop_code`, `unit_code`, `building`, `province`, `beds`, `sqft`, `month` (pandas Period[M]), `asking_rent`.

**Units / listings** (`UNITS`): `unit_id`, `prop_code`, `unit_code`, `building`, `province`, `beds`, `baths`, `sqft`, `floor`, `unit_type`, `listing_asking_rent` (= `sRent`), `snapshot_month` (= `sAsOf`, varies by unit!), `available_date`.

**Pairs** (`PAIRS`, produced by MSR `build_pairs`): `unit_id`, `prop_code`, `building`, `province`, `beds`, `is_renewal`, `prev_lease_start`, `lease_start`, `sign_date`, `year` (of lease_start), `gap_years`, `rent_contract_prev`, `rent_contract`, `rent_net_prev`, `rent_net`, `loggrowth_contract` (annualized log), `loggrowth_net` (annualized log), `eligible` (bool), `exclusion_reason` (str or empty).

**Concession links** (`LINKS`, FCT): `concession_id`, `unit_id`, `lease_start` (of assigned lease, NaT if unresolved), `n_candidates`, `rule`, `status` ∈ {`unique`,`resolved_by_fit`,`unresolved`}, `recon_error`.

**External observations** (`data/public/sources.csv`, MSR): `series_id`, `publisher`, `geography`, `metric`, `unit`, `ref_period_start`, `ref_period_end`, `value`, `release_date`, `url`, `location_in_source`, `accessed_date`, `extracted_by` ∈ {`manual`,`llm`}, `verified_by`, `notes`.

### 7.2 Dataclasses
- `CanonicalTables(leases, concessions, asking, units)`
- `Snapshot(cutoff, leases, concessions, asking, units, external)` — everything already filtered to what was knowable at `cutoff`.
- `ForecastResult(target_year, cutoff, headline_net_pct, headline_contract_pct, median_net_pct, median_contract_pct, segments: DataFrame, components: dict, model_name: str, assumptions: list[str])`
- `BacktestResult(target_year, forecast: ForecastResult, actual_net_pct, actual_contract_pct, error_pp_net, error_pp_contract, coverage: dict)`

### 7.3 Function signatures (owners implement exactly these)
| Function | Owner | Signature |
|---|---|---|
| load raw | INT | `io.load.load_raw(data_dir) -> dict[str, DataFrame]` (verifies SHA-256 vs manifest) |
| canonicalize | INT | `io.dictionary.canonicalize(raw) -> CanonicalTables` |
| QA report | INT | `io.qa.run_qa(raw, tables, data_end_date) -> DataFrame` (check, status, count, detail) |
| pairs | MSR | `measure.pairs.build_pairs(leases, cfg) -> DataFrame[PAIRS]` |
| composition | MSR | `measure.composition.rent_bridge(leases, pairs, cfg) -> DataFrame` |
| renewal split | MSR | `measure.renewals.split_summary(pairs, cfg) -> DataFrame` |
| external | MSR | `market.registry.load_external(path) -> DataFrame`; `market.registry.as_of(external, cutoff) -> DataFrame` |
| asking signal | MSR | `market.asking.turnover_signal(snapshot, cfg) -> DataFrame` (segment, expected log growth for turnovers) |
| regulation | MSR | `market.regulation.applicability_matrix(cfg) -> DataFrame` |
| snapshot | FCT | `forecast.asof.make_snapshot(tables, external, cutoff) -> Snapshot` |
| incentives | FCT | `incentives.engine.forecast_discount(snapshot, cfg) -> DataFrame` (segment, d0, d1) |
| concession links | FCT | `incentives.linking.link_concessions(concessions, leases, cfg) -> DataFrame[LINKS]` |
| forecast | FCT | `forecast.combine.forecast(snapshot, cfg) -> ForecastResult` |
| actual | FCT | `evaluate.backtest.actual_for_year(tables, year, weights, cfg) -> dict` |
| backtest | FCT | `evaluate.backtest.run_backtest(tables, external, target_year, cfg) -> BacktestResult` |
| bootstrap | INT | `evaluate.uncertainty.unit_bootstrap(tables, external, cfg, n_boot) -> DataFrame` |
| export | INT | `export.aggregates.export(results, path) -> None` (aggregates only, JSON) |

Notebook-facing wrappers (section 10, FCT) keep the sponsor signatures:
```python
def estimate_2026(leases, asking, external=None) -> float      # returns headline % (net of incentives)
def backtest(leases, target_year) -> BacktestResult            # delegates to run_backtest, same pipeline
```
`backtest()` must call the same `forecast()` used by `estimate_2026()`. No separate easier method.

---

## 8. Configuration (no magic numbers)

- Every number with meaning goes in YAML: dates, cutoffs, gap bounds, quantiles, windows, weights, seeds, bootstrap counts, scenario levers.
- Code reads config through `leaselens.config.load_config()` (INT), which merges `core.yaml`, `measure.yaml`, `forecast.yaml` into one object. Each key lives in exactly one file.
- Allowed literals in code: 0, 1, −1, 100 (for %), 12 (months/year), 365.25 (days/year) when named as constants in `contracts.py`.
- Each YAML key gets a one-line comment explaining what it is and why that value.

---

## 9. Shared analytical decisions (agreed; do not change without INT)

### 9.1 Headline definition
**"Fixed-composition same-unit growth in rent net of all incentives, 2026."**
- For each eligible pair (consecutive leases of the same unit), annualized log growth: `ln(P_i / P_{i-1}) / gap_years`, where P = `rent_net_all_incentives`.
- Winsorize log growth at quantiles set in `measure.yaml`, with thresholds learned on **training data only**.
- Segment = `prop_code × beds × is_renewal`. Segment mean log growth, weighted by **fixed weights** = segment shares of eligible pairs in the window before the cutoff (window length in `core.yaml`). Weights are frozen at each cutoff.
- Headline % = `100 × (exp(Σ w_s × mean_s) − 1)`.
- Companions (always reported next to it): same thing on `rent_contract`; plain medians of both.
- Why log-mean: segment forecasts aggregate exactly; the composition waterfall and the contractual→net bridge are exactly additive. The median is the robustness check.
- Weights describe the mix of observed lease transitions, NOT portfolio occupancy or turnover rate. Say so wherever weights appear.

### 9.2 Pair eligibility (starting values, sensitivity reported)
- Same `unit_id` (cross-checked against `prop_code + unit_code`), consecutive by `lease_start`.
- `gap_years` strictly between the bounds in `measure.yaml` (starter: 0.5 and 2.5). Report sensitivity including 6-month leases.
- Both rents positive. Every rejected pair keeps an `exclusion_reason`.
- A pair belongs to the calendar year of its later `lease_start`.

### 9.3 Time / leakage policy
- Cutoff for forecasting year y = December 31 of y−1. 2026 → 2025-12-31.
- Training uses leases with **both** `sign_date` and `lease_start` ≤ cutoff.
- Asking: months ≤ cutoff. Concessions: `date_from` ≤ cutoff. Listings snapshot is 2025 data: never used for historical folds.
- External data: `release_date` ≤ cutoff. Québec's December 17 2025 method change and January 19 2026 percentage are post-cutoff → separate labelled scenario only.
- Any threshold, weight, quantile or model is fit on training data only.
- Test: appending fake future rows must not change the forecast (FCT `test_asof_leakage.py`).

### 9.4 Interpretation guardrails
- `rent_net_all_incentives` is concession-adjusted rent, not cash collected.
- Regional vacancy (CMHC) = market context only. Never a project occupancy figure.
- the Ontario new-build: Ontario regime; central scenario = post-November-15-2018 first-occupancy exemption is plausible (building first leased 2023), alternative scenario = guideline applies. Never a legal determination.
- Québec newer buildings (Building, Building, Building phase 3): possible new-building clause → scenario note only.
- Three backtest years support weak conclusions. Call scenario ranges "scenarios", not prediction intervals.

---

## 10. Task lists per track

Task IDs are referenced in branches, PRs and Handback Reports. Do tasks in order unless INT says otherwise. Hours are wall-clock targets from kickoff (H0).

### INT — Integration & Product (Yousef) — ~13 h
| ID | Target | Task | Done when |
|---|---|---|---|
| I-01 | H0–H1 | Scaffold repo per Section 4; `pyproject.toml`, `requirements.txt`, `.gitignore`, `.env.example`, pre-commit (nbstripout, block CSV outside public/synthetic, block `.env`, large-file check), empty owned files for every track with docstring stubs | Partners can branch and `pytest` runs green |
| I-02 | H0–H1 | `contracts.py` (Section 7), `config.py`, `config/core.yaml`, stub `measure.yaml`/`forecast.yaml` with agreed keys | Contracts merged; announced frozen |
| I-03 | H0–H1 | `make_synthetic.py` → `data/synthetic/` with the 4 tables in source schema (incl. leading-zero unit codes, an `sSite` collision, PromoPay lumps, renewals, a new building) + `conftest.py` fixtures | All tracks can test without CRM |
| I-04 | H1–H2 | `io/load.py` (typed load, SHA-256 vs `manifest.json`), `io/dictionary.py` (Section 7.1), `io/qa.py`; section `02_data_dictionary_qa.py` | QA table prints counts only; hashes verified |
| I-05 | H1–H3 | `build_notebook.py`: jupytext sections → `project_analysis.ipynb`, execute on clean kernel, fail on error; works on synthetic mode via `core.yaml` flag | One command builds the notebook |
| I-06 | continuous | Review + merge PRs (check ownership diff, tests, privacy); maintain `docs/rubric_checklist.md` | `dev` always green |
| I-07 | H4 | Integration #1: pairs (MSR) + snapshot (FCT) + loaders on real data, counts-only smoke run | Smoke script passes locally |
| I-08 | H4–H6 | `evaluate/uncertainty.py`: unit-cluster bootstrap (resample whole unit histories, recompute headline); section `11a_uncertainty.py` | Interval reproducible with fixed seed |
| I-09 | H6–H8 | `export/aggregates.py` + `scripts/export_aggregates.py`: headline, companions, backtest table, coverage, scenario range → `outputs/private/aggregates.json` | JSON has no unit-level data (test) |
| I-10 | H8 | Integration #2 / **core freeze**: full notebook build on real data | Notebook runs top to bottom |
| I-11 | H8–H11 | Streamlit app (Overview, Why, Validation, Scenarios & Sources) reading only `aggregates.json`; synthetic demo mode | App runs offline |
| I-12 | H9–H11 | `app/narrative.py` (LLM, FR/EN evidence card from aggregates JSON only) + `app/number_guard.py` (reject any number not in the JSON) + `app/cache/` fallback | Guard test passes; works with no key |
| I-13 | H6–H11 | Sections `00_executive.py`, `01_definition.py` (Section 9.1 in French), `12_references.py` (compile `docs/references/*.md`, cite starter, data, AI tools) | Narrative numbers come from results |
| I-14 | H11–H12.5 | Final build, clean kernel, fix-request round | Clean run |
| I-15 | H12.5–H14 | README (run steps, versions, sources, AI tools), final privacy check (`git ls-files` scan), submission package, slides for own sections | Submitted |

### MSR — Measure & Market (Hamza) — ~13 h
| ID | Target | Task | Done when |
|---|---|---|---|
| M-01 | H0–H1 | Read contracts; fill `measure.yaml` keys (gap bounds, winsor quantiles, strata); write failing tests for pairs (constant price → 0 growth; 12-month doubling → ~100%; unsafe key collides; safe key doesn't) | Tests written on synthetic |
| M-02 | H1–H2.5 | `measure/pairs.py` `build_pairs` with `exclusion_reason`, gap sensitivity helper; **merged by H2.5** (FCT depends on it) | Tests pass; counts-only real run |
| M-03 | H2.5–H5 | `market/registry.py` + `scripts/extract_sources.py` (LLM reads PUBLIC pages → `sources_draft.csv`); human-verify into `sources.csv`. Minimum panel: CMHC Montréal & Ottawa (same-sample growth, turnover vs non-turnover if available, vacancy as context), StatCan 18-10-0004-01 rent CPI QC & ON, TAL historical parameters, Ontario guidelines 2023–2026, with `release_date` for each | `as_of()` rejects post-cutoff rows (test) |
| M-04 | H5–H6 | `market/asking.py` `turnover_signal`: asking posted before cutoff vs prior rent, minus asking→signed spread learned on training years | Merged by H6 (FCT combines at H6–H8) |
| M-05 | H6–H8 | `measure/composition.py` `rent_bridge`: naïve median vs fixed-mix same-unit vs contractual→net; section `03_composition.py`; section `04_matching.py` (safe vs unsafe key demo with counts, exclusion audit, coverage, gap sensitivity) | Core sections done by freeze |
| M-06 | H8–H10 | `measure/renewals.py` + `market/regulation.py` (QC/ON applicability matrix, regulatory reference lines, Met scenarios); section `06_renewals_regulation.py` | Renewal vs turnover by province with counts |
| M-07 | H10–H11 | `market/reconcile_market.py`: internal same-unit vs CMHC/CPI trends per CMA; section `07_external.py` with provenance table | Reconciliation chart + source table |
| M-08 | H11–H11.5 | French Markdown pass on own sections; `docs/references/MSR.md` complete | Ready for final build |
| M-09 | H12.5–H14 | Slides for own sections; rehearsal | — |

### FCT — Incentives & Forecast (Yousif) — ~13 h
| ID | Target | Task | Done when |
|---|---|---|---|
| F-01 | H0–H1 | Read contracts; fill `forecast.yaml` keys; write leakage test first (append future rows → identical forecast; post-cutoff external row rejected) | Tests written on synthetic |
| F-02 | H1–H3 | `forecast/asof.py` `make_snapshot`; `forecast/baselines.py` (B0 last year, B1 trailing mean, B2 market anchor + gap); `evaluate/metrics.py` (signed + absolute error in pp); `evaluate/backtest.py` skeleton incl. `actual_for_year` with frozen weights | Baselines backtest on synthetic |
| F-03 | H3–H4.5 | `incentives/engine.py` `forecast_discount`: discount share trend per segment (renewal vs turnover separately) | Test: hypothetical 5% contract + 1 free month ≈ −3.75% net |
| F-04 | H4.5–H6.5 | `forecast/monthly_index.py` (monthly same-unit index from PAIRS) + `forecast/nowcast.py` (small state-space / local-trend model; config-driven) | Index + nowcast on real data, counts/aggregates only |
| F-05 | H6.5–H8 | `forecast/combine.py`: renewal engine + turnover engine (uses MSR `turnover_signal`) + incentive engine → fixed-weight aggregation → `ForecastResult`; `run_backtest` 2023–25 for all baselines + engine model | **Core freeze**: backtest table exists |
| F-06 | H8–H10 | `incentives/linking.py` + `incentives/reconcile.py`: concession→lease reconciliation matcher (candidates = same unit, signed on/before, active; score by reconciliation fit; status unique / resolved_by_fit / unresolved); section `05_concessions.py` (PromoPay lump evidence, accessory inclusion, reconciliation rate, 2024+ divergence explained) | Reconciliation rate reported; no amount multiplication (test) |
| F-07 | H10–H11 | Champion selection (pre-declared: choose on 2023–24, 2025 held out); `forecast/scenarios.py` (incentive intensity, renewal mix, Met applicability, post-cutoff QC scenario); per building × beds forecasts with shrinkage; save model to `models/` if a fitted model is used | Scenario table low/central/high |
| F-08 | H10–H11.5 | Sections `08_forecast_method.py`, `09_backtest.py`, `10_forecast_2026.py` (wrappers `estimate_2026`, `backtest`), `11b_scenarios.py` in French | Ready for final build |
| F-09 | H12.5–H14 | Slides for own sections; rehearsal | — |

### Critical-path dependencies
- I-01/I-02/I-03 → everyone (H1). **Highest priority of the whole project.**
- M-02 (pairs, H2.5) → F-04, F-05, I-08.
- M-03 (external, H5) → F-02 B2 baseline, F-05.
- M-04 (asking signal, H6) → F-05.
- F-05 (forecast + backtest, H8) → I-08 final run, I-09, I-11, I-12.
- Until a dependency lands, build against synthetic fixtures and the contract signature.

### Sync points (all three, 10 minutes max)
H1 contracts frozen · H4 integration #1 · H8 core freeze · H11 feature freeze · H12.5 notebook frozen · H14 submit.

### Cut order if behind schedule (INT decides)
1. LLM narrative → static evidence card. 2. Post-cutoff Québec scenario. 3. Per building × beds shrinkage. 4. Bootstrap (keep scenarios). 5. Nowcast → simple trailing trend. Never cut: matching audit, concession analysis, external data with release dates, backtests, Markdown.

---

## 11. Coding standards

- Python 3.11. pandas, numpy, scikit-learn, matplotlib (+ statsmodels if installable; otherwise implement the small models directly). New packages only via change request.
- Type hints on public functions. Docstrings (English) stating inputs, outputs, assumptions.
- Pure functions: take tables + config, return new tables. No hidden global state, no reading files inside analysis functions (only `io/` reads files).
- Read IDs as strings (`dtype=str` for `hUnit`, `hProperty`, `hBuilding`, `sPropCode`, `sUnitCode`). Parse dates once in `io/`.
- Never use `sSite` as a key. `sSite` may appear only in the collision demonstration.
- Names: snake_case; columns per Section 7.1; no abbreviations other than `pct`, `pp`, `qc`, `on`.
- Charts: matplotlib, readable fonts, colorblind-safe palette, contractual vs net colors consistent everywhere (INT defines in `contracts.py`: `COLOR_CONTRACT`, `COLOR_NET`). Target 6–8 high-value figures in the whole notebook.
- Deterministic: seeds from `core.yaml`.
- Every exclusion, clip or drop is counted and reported.

### Notebook section files (jupytext percent format)
```python
# %% [markdown]
# ## 4. Appariement à unité constante
# **Entrée :** ... **Opération :** ... **Pourquoi :** ... **Vérification :** ...

# %%
pairs = build_pairs(tables.leases, cfg)
```
- Each section starts with a Markdown cell stating input, operation, rationale, checks.
- One Markdown cell before every data-changing step.
- Sections import from `leaselens`; they do not redefine library functions.
- Section files must run standalone given the shared setup cell from `00_executive.py` (INT provides `tables`, `cfg`, `external`).
- Numbers in Markdown text must be produced by code (f-strings in a `display(Markdown(...))` cell) or updated after the final run.

---

## 12. Handback Report (end every task with exactly this)

```
### HANDBACK — <TRACK> <task-id> <short title>
Branch: <name>        PR: <link or "not opened">
Files changed (all owned by <TRACK>): <list>
What was built: <3–6 bullets>
Contract compliance: <functions/columns implemented exactly as Section 7, or deviations>
Tests: <command> → <pass/fail counts>; new tests: <list>
Real-data check (counts/aggregates ONLY): <e.g. "eligible pairs: N; excluded by reason: {...}">
Decisions made: <bullets; also appended to docs/decisions/<TRACK>.md>
Assumptions: <bullets; also appended to docs/assumptions/<TRACK>.md>
Change requests filed: <REQUEST ids or none>
Blockers / questions for human: <list or none>
Next task: <id>
```
No raw rows, unit codes or `hUnit` values in the report.

---

## 12b. Working loop (human ⇄ Claude chat ⇄ Claude Code)

Each teammate works with two AI tools:
- **Claude (chat, inside the HALO project)** plans the task and writes the Claude Code prompt; reviews what comes back.
- **Claude Code (in the local repo)** executes the prompt, runs tests, commits on the feature branch, and ends with the Handback Report.

Loop per task: chat writes prompt → human pastes into Claude Code → Claude Code works and prints the Handback Report → human pastes the report (and any error output) back into the chat → chat reviews and either approves ("open the PR into dev") or writes a fix prompt. Target: **one prompt + at most two fix rounds per task.** Relay per task, not per command: give Claude Code whole tasks, not single steps.

Never paste raw CRM rows into either tool's chat. Handback Reports contain counts and aggregates only.

## 12c. Autopilot protocol (`/next`)

The repo is self-directing so nobody has to hand-write task prompts:
- **`.track`** (local, gitignored) holds your track code. Claude Code reads it to know whose agent it is.
- **`docs/board/<TRACK>.md`** is your track's static task list (ID, task, dependencies, notes). Status is never written there.
- **`scripts/board_status.py`** computes status from git: **done** = task ID appears in a commit message on `origin/dev`
  (or the row's Notes start with `done`); **in review** = a remote branch `<prefix><ID>-…` exists; **todo** = neither.
  It prints the next workable task per track.
- **`/next`** (`.claude/commands/next.md`): sync `dev` → run the status script → branch `<prefix><ID>-<name>` → build →
  test → commit `[<TRACK>][<ID>] …` → push branch → open PR into `dev` → print Handback Report → stop.
- **`/status`** shows all boards. **`/review-pr <n>`** (INT) pre-checks a PR before merging.
- Because status lives in git, two open PRs from the same person never conflict on a board file.
- Task ID in the branch name and the commit subject is mandatory; the status script depends on it.

Humans: type `/next`, open the PR if only a link was printed, tell INT, type `/next` again. Come back to the planning chat only at sync points or when the agent stops on a Section 13 condition.

## 13. When an agent must STOP and ask the human

- The task requires editing a file not owned by the current track.
- A contract (Section 7) or shared decision (Section 9) seems wrong or insufficient.
- Anything would expose CRM rows (commit, print, API call, chart with unit labels).
- A data finding contradicts this file (e.g. a key is not unique, a column means something else).
- A result changes the headline by more than the tolerance in `core.yaml` and you don't know why.
- Tests fail for reasons outside your files.
- You're tempted to add a new dependency, new top-level folder or new feature not in your task list.

Never resolve these by guessing. State the problem, the options, and your recommendation.

---

## 14. Definition of done (every task)

- [ ] Only owned files changed (`git diff --name-only`).
- [ ] Matches contracts and config; no magic numbers.
- [ ] Tests on synthetic data pass; new behavior has a meaningful test.
- [ ] Real-data check printed counts/aggregates only.
- [ ] Markdown (French) explains any data-changing step in your sections.
- [ ] Decisions and assumptions logged in your `docs/` files.
- [ ] pre-commit passes; no CSV/outputs/secrets staged.
- [ ] Handback Report produced.

---

## 15. Final submission checklist (INT, H12.5–H14)

- [ ] `python scripts/build_notebook.py --real` runs on a clean kernel from an up-to-date `dev`.
- [ ] PR `dev → main` merged and tagged `v-submission`; submission built from `main`.
- [ ] Headline %, definition, companions and scenario range appear in section 00 and match `aggregates.json`.
- [ ] `estimate_2026()` and `backtest()` work with the sponsor signatures; backtests for 2023/2024/2025 shown with errors in pp for every model, including losers.
- [ ] Sources cited with URLs and release dates; starter credited; AI tools cited.
- [ ] `git ls-files` contains no CRM file, no outputs/private, no models, no `.env`.
- [ ] README: setup, run commands, versions, data placement (`data/private/`), AI usage.
- [ ] App runs from `aggregates.json` only; synthetic demo mode works.
- [ ] Mentor confirmed whether aggregate charts may be embedded in the submitted notebook.
