# Halo Lens — Rent-growth forecast

Halo Lens (code package: `leaselens`).

> **FR —** Halo Lens estime la hausse de loyer 2026 d'un portefeuille résidentiel (immeubles au Québec et en Ontario) à partir de l'historique des baux et de données publiques. Nous définissons précisément la hausse mesurée, comparons chaque unité à elle-même, traitons explicitement les concessions, séparons renouvellements et relocations selon les règles de chaque province, et validons la méthode par backtest sur 2023, 2024 et 2025.

> **EN —** Halo Lens estimates a residential portfolio's 2026 rent increase from lease history and public market data. We define exactly what "rent increase" means, compare each unit with itself, handle incentives explicitly, separate renewals from turnovers under each province's rules, and validate the method by backtesting 2023, 2024 and 2025.

---

## Pour le jury / For the jury

**Vous avez besoin de / You need:** Python 3.11, 3.12 ou / or 3.13 (testé / tested: 3.11.17, 3.12.15, 3.13.15), les quatre fichiers CSV de project et `manifest.json`, et ce dépôt. / the four project CSV files and `manifest.json`, and this repository.

Quatre commandes, depuis le dossier du dépôt / Four commands, from the repository folder:

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux : source .venv/bin/activate
pip install -r requirements.txt
jupyter lab project_analysis.ipynb  # puis / then : Run > Run All Cells (kernel : .venv)
```

**Où mettre les CSV / Where to put the CSV files:** dans un dossier de votre choix (par exemple `C:\project-data`), avec les 4 fichiers `portfolio_*.csv` et `manifest.json`. Indiquez ce dossier, au choix / Point to that folder, either by setting `DATA_DIR = r"C:\project-data"` at the top of the first cell of the notebook, or with the environment variable `LEASELENS_DATA_DIR`. Sans réglage, le notebook lit `data/private/`. / Without a setting, the notebook reads `data/private/`.

Si un fichier manque, le notebook s'arrête et indique les fichiers attendus. Si un paquet manque, il indique `pip install -r requirements.txt`. Les empreintes SHA-256 sont vérifiées avant toute lecture. / If a file is missing, the notebook stops and lists the expected files. If a package is missing, it asks you to run `pip install -r requirements.txt`. The SHA-256 hashes are checked before any file is read.

**Durée attendue / Expected run time :** environ 6 à 12 minutes selon la machine (le bootstrap §11a et les sensibilités §11b sont les plus longs), plus environ 8 minutes pour `pip install` / about 6–12 minutes depending on the machine (bootstrap §11a and sensitivities §11b are the slowest), plus about 8 minutes for `pip install`.

**Sorties / Outputs:** les figures sont intégrées au notebook. Les sorties calculées sur vos fichiers restent sur votre machine. / The figures are embedded in the notebook. Outputs computed from your files stay on your machine.

---

## Contents

1. [The answer](#1-the-answer)
2. [Method in one page](#2-method-in-one-page)
3. [Quick start](#3-quick-start)
4. [Repository layout](#4-repository-layout)
5. [Data and confidentiality](#5-data-and-confidentiality)
6. [Team workflow](#6-team-workflow)
7. [Reproducibility](#7-reproducibility)
8. [Sources](#8-sources)
9. [AI tools used](#9-ai-tools-used)
10. [Acknowledgements](#10-acknowledgements)

---

## 1. The answer

| | Value |
|---|---|
| **2026 headline** | See **section 00** of the submitted notebook `project_analysis.ipynb` (executed; the figures are computed from the CRM files and are not written in this README) |
| Definition | Fixed-composition same-unit growth in rent net of all incentives |
| Contractual companion | Section 00 of the notebook |
| Scenario range (low / central / high) | Section 00 and section 11b of the notebook |
| Forecast as of | 2025-12-31 for CRM data; public data released by 2026-01-31 (no 2026 CRM information used) |
| Backtest error, 2023 / 2024 / 2025 (pp) | Section 09 of the notebook |

Every figure is produced by `project_analysis.ipynb`; none is typed by hand, and this README carries no real figure.

**Modèle entraîné / Trained model:** none. The champion (B0) is a transparent rule; all parameters live in `config/*.yaml`.

### 1.1 What makes Halo Lens different

- **Same-unit pairs on a safe key.** Each lease is compared with the previous lease of the same unit, matched on `hUnit` and on `sPropCode + sUnitCode`, never on `sSite + sUnitCode`, which merges distinct apartments. The notebook shows the collision with counts.
- **Concession → lease reconciliation.** A matcher links each concession credit to the lease it belongs to. `PromoPay` is treated as a lump credit and accessory credits are included, so net rent is explained rather than assumed.
- **Québec and Ontario kept apart.** Renewals and turnovers are separated, and the five Québec buildings and the Ontario new-build are read under their own rules (TAL, Ontario guideline). the Ontario new-build's exemption is shown with its evidence as a scenario, never as a legal determination.
- **Information-date discipline.** CRM data stops at December 31 of the previous year; public data counts if released by January 31 of the target year (approved by the mentor); the strict December 31 version is reported as a sensitivity; a leakage test shows that appending future rows does not change the forecast.
- **A champion chosen before the results.** The selection rule was declared in advance and is kept even when another model did better on the holdout year.
- **Three ways of showing uncertainty.** Scenarios, one-at-a-time sensitivities (a tornado chart), and a unit-cluster bootstrap that resamples whole unit histories. They are not prediction intervals.
- **An AI layer behind a privacy wall.** The Claude API sees only public pages or the aggregates file, never CRM rows. A number guard rejects any figure that is not in the results, and a source watcher re-checks the official pages.

### 1.2 Deliverables

| Item | Where |
|---|---|
| Notebook with `estimate_2026()` and `backtest()` | Section 10 of `project_analysis.ipynb` |
| Final percentage and its definition | Sections 00 and 10 (computed, not written in this README); the definition is section 01 |
| Run instructions, versions, references | This README (jury section and quick start) and section 12 of the notebook |
| Trained model | None saved. The champion is a rule over the data, not a fitted artefact; all parameters live in `config/*.yaml` |
| Jury presentation | Prepared by the team separately; it is not part of this repository |
| Submission package | `python scripts/make_submission.py` writes `outputs/submission/HaloLens_submission.zip` (code, synthetic fixtures and the executed notebook; no CRM files) |

Tested on Python 3.11, 3.12 and 3.13. Expected run time: see the jury section above (about 6 to 12 minutes for the notebook, plus about 8 minutes for `pip install`).

### 1.3 Rubric → evidence

| Criterion | Where in the notebook |
|---|---|
| Definition of the increase | Section 01 (and the answer in section 00) |
| Data analysis and composition effects | Sections 02 and 03 |
| Same-unit lease matching | Section 04 |
| Concessions | Section 05 |
| Renewals vs turnovers, Québec vs Ontario | Section 06 |
| External data | Section 07 |
| Forecast and backtest | Sections 08 to 10, 11a and 11b |
| Notebook quality | A Markdown cell before every data-changing step; the notebook is built from jupytext sources in `notebook/sections/`; the code is covered by tests |

## 2. Method in one page

**What we measure.** For each pair of consecutive leases of the same unit, the annualized log growth of monthly rent net of all incentives. Segment averages (property × bedrooms × renewal/turnover) are combined with weights frozen at the forecast date, so a change in portfolio mix can't masquerade as a price change. We always report the contractual-rent version and plain medians next to it.

**Why not the median of all leases?** Because it mostly measures composition. New premium buildings entering the portfolio push the median up even when no tenant pays more. The notebook shows this effect and decomposes it.

**Same-unit matching.** Units are matched on `sPropCode + sUnitCode`, cross-checked against `hUnit` and `sLink`. We demonstrate why `sSite + sUnitCode` is unsafe (it merges distinct apartments) and keep a reason for every excluded pair.

**Concessions.** We verify what `sRentEffective` actually contains by reconciling it against the concession records, show that `PromoPay` is a one-off credit rather than a monthly discount, and explain why contractual and net growth diverge from 2024 onward.

**Renewals vs turnovers.** Analysed separately, and interpreted under the applicable regime: Québec's Tribunal administratif du logement for five buildings, Ontario's rent-increase guideline for the Ontario new-build (with its applicability treated as an explicit scenario, not a legal determination).

**External data.** CMHC rental market survey (Montréal and Ottawa), Statistics Canada rent CPI (Québec and Ontario), TAL parameters and Ontario guidelines. Every observation carries its **release date**, and a backtest only sees what had been published at its forecast date.

**Forecast.** Three engines combined with fixed weights:
- *Renewal engine* — regulated increases for sitting tenants.
- *Turnover engine* — market-driven relets, using asking rents posted before the forecast date as a leading indicator.
- *Incentive engine* — the trend in incentive intensity, which converts contractual growth into net growth.

These compete against simple baselines (last year's growth, trailing average, market anchor). The model is chosen on 2023–2024 and 2025 is kept as a final check. All results, including models that lose, are shown.

**Uncertainty.** A unit-level bootstrap for sampling uncertainty, plus low / central / high scenarios for incentive intensity, renewal mix and Ontario applicability. Scenario ranges are scenarios, not calibrated prediction intervals.

**What this extract cannot tell us.** Occupancy, vacancy, absorption or total rent roll. We never compute or quote them.

## 3. Quick start

### Prerequisites
- Python 3.11, 3.12 or 3.13. Tested with `requirements.txt` on 3.11.17 (pandas 2.3.3, numpy 2.4.6, scipy 1.17.1), 3.12.15 and 3.13.15 (pandas 2.3.3, numpy 2.5.3, scipy 1.18.1, scikit-learn 1.9.1, statsmodels 0.14.6, matplotlib 3.11.2). The full notebook was run top to bottom on 3.13.15 in a fresh venv.
- Git
- The sponsor's data package (`project-participants.zip`), obtained privately — it is **not** in this repository

### Setup

```bash
git clone https://github.com/YousefAkay/HALO.git
cd HALO
git switch dev
python -m venv .venv
```

Activate the environment:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate
```

Install and configure:

```bash
pip install -r requirements.txt
pre-commit install
```

### Add the data

Unzip the sponsor package into `data/private/` (create the folder if needed). It should contain the four `portfolio_*.csv` files, `manifest.json` and `template.ipynb`. The loader verifies every file against the SHA-256 hashes in `manifest.json` and refuses to run if anything has changed.

### Run

| Task | Command |
|---|---|
| Tests (synthetic data, no CRM needed) | `pytest -q` |
| Build and execute the notebook on synthetic data | `python scripts/build_notebook.py --synthetic` |
| Build and execute the notebook on the real data | `python scripts/build_notebook.py --real` |
| Export aggregate results for the app (real data, or `--synthetic`) | `python scripts/export_aggregates.py --real` |
| Launch the dashboard | `streamlit run app/streamlit_app.py` |

The notebook can also be opened directly in Jupyter (`project_analysis.ipynb`) and run top to bottom on a clean kernel.

### Optional: AI features

Three features call the Claude API, always on public pages or on aggregates, never on CRM rows: extracting public-source values into `data/public/sources_draft.csv`, the source watcher (`python scripts/extract_sources.py --watch`, public pages only), and the dashboard's scenario copilot and Q&A over the aggregates, with a number guard that rejects any figure not in the results. To enable them, copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. Without a key the dashboard keeps its scenario dropdowns and, in the synthetic demo only, validated cached answers; **the notebook and forecast never need a key.**

### Run the dashboard on real data

```bash
python scripts/export_aggregates.py --real     # writes outputs/private/aggregates.json (gitignored)
streamlit run app/streamlit_app.py             # choose "Real (outputs/private)" in the sidebar
```

Demo mode (the default, synthetic data) works without any data or key: `streamlit run app/streamlit_app.py`.

## 4. Repository layout

```
HALO/
├─ project_analysis.ipynb      graded notebook (generated from notebook/sections/)
├─ notebook/sections/        one file per notebook section
├─ src/leaselens/            analysis library
│  ├─ io/                    loading, hash checks, data dictionary, QA
│  ├─ measure/               same-unit pairs, composition, renewals
│  ├─ market/                public sources, asking rents, regulation
│  ├─ incentives/            incentive engine, concession→lease reconciliation
│  ├─ forecast/              as-of snapshots, baselines, index, nowcast, combination
│  ├─ evaluate/              backtests, metrics, uncertainty
│  └─ export/                aggregate export for the app
├─ config/                   every threshold and date (no magic numbers in code)
├─ scripts/                  notebook build, source extraction, export
├─ app/                      Streamlit dashboard
├─ data/public/              public-source extracts with release dates
├─ data/synthetic/           invented fixtures for tests and the public demo
├─ tests/                    invariants and leakage tests
└─ docs/                     decisions, assumptions, references, rubric checklist
```

The full layout, file ownership and coding rules are in [`AGENTS.md`](AGENTS.md).

## 5. Data and confidentiality

The CRM extract provided by project is confidential. Under the challenge rules it may not be published, uploaded to GitHub (even privately) or Kaggle, or included in deliverables.

- CRM files live only in `data/private/`, which is gitignored.
- Anything computed from CRM data goes to `outputs/private/`, also gitignored.
- Source files are never modified; all renaming and transformation happens in code.
- The notebook shows aggregates only — no individual leases, unit codes or identifiers.
- The dashboard reads only an aggregate results file and includes a fully synthetic demo mode.
- Pre-commit hooks block CSV files outside `data/public/` and `data/synthetic/`, notebook outputs and `.env`.

**The CSV files in this repository are not project data.** `data/synthetic/` holds invented test files generated by `scripts/make_synthetic.py`: same column format as the sponsor files, fake values (see [`data/synthetic/README.md`](data/synthetic/README.md)). `data/public/` holds public statistics from Statistics Canada, the TAL, Ontario and CMHC, each with its source URL and release date.

## 6. Team workflow

| Track | Owner | Responsibility |
|---|---|---|
| INT — Integration & Product | Yousef | Repo, contracts, data loading, notebook assembly, uncertainty, dashboard |
| MSR — Measure & Market | _Hamza_ | Matching, composition, renewals, regulation, public data |
| FCT — Incentives & Forecast | _Yousif_ | Leakage-safe pipeline, incentives, forecasting, backtests, scenarios |

- `main` holds submission-ready work only. `dev` is the integration branch.
- Every change goes through a pull request from a feature branch (`int/…`, `msr/…`, `fct/…`) into `dev`. Nobody pushes to `dev` or `main` directly; a pre-push hook (installed by `pre-commit install`) enforces this.
- Each file has exactly one owning track. Cross-track changes go through `docs/requests/`.
- Each teammate's Claude Code works through its track's board in `docs/board/` with the `/next` command.
- New teammates start with [`TEAMMATE_KICKOFF.md`](TEAMMATE_KICKOFF.md).

## 7. Reproducibility

- Library versions are pinned in `requirements.txt`.
- Random seeds are set in `config/core.yaml`.
- Input files are verified by SHA-256 before every run.
- The forecast for year *y* uses only information available on December 31 of *y − 1*; an automated test confirms that adding future records doesn't change it.
- The notebook is executed on a clean kernel by `scripts/build_notebook.py` before every release to `main`.

## 8. Sources

Primary challenge material: project's `instructions.pdf`, `template.ipynb`, `presentation-project.pdf` and the CRM extract (confidential).

Public data (full provenance, reference periods and release dates in `data/public/sources.csv`):

- CMHC — Rental Market Survey and Rental Market Report: <https://www.cmhc-schl.gc.ca>
- Statistics Canada — Consumer Price Index, table 18-10-0004-01: <https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401>
- Tribunal administratif du logement — rent adjustment calculation: <https://www.tal.gouv.qc.ca>
- Government of Ontario — residential rent increase guideline: <https://www.ontario.ca/page/rent-increase-guideline>

Articles and other references are listed in the notebook's References section.

## 9. AI tools used

As required by the challenge rules:

| Tool | Use |
|---|---|
| Claude (Anthropic), chat | Planning and review of the method and the tasks |
| Claude Code (Anthropic) | Implementation, tests, and an AI pre-merge review of every pull request |
| Claude API (Anthropic) | (1) Extracting values from public web pages into a draft source table, checked against the official pages by Claude, with a human spot-check of a named sample (`docs/assumptions/MSR.md`); (2) the source watcher, which re-reads the official pages (public pages only); (3) the dashboard's scenario copilot and Q&A over the aggregates, with a number guard that rejects any figure absent from the results |

**No CRM data was sent to any API.** The API receives only public pages, the aggregates file (counts and percentages, no unit-level field by schema), committed notes with real-data numbers removed, and the user's question. The forecast itself is produced by the documented statistical method, not by an AI model.

## 10. Acknowledgements

Thanks to project for the challenge, data and mentoring. Our notebook builds on the sponsor's `template.ipynb`; reused cells and ideas are credited where they appear. Original contributions: the target definition, the release-date-aware validation framework, the concession reconciliation, the external-data integration, the model comparison, the uncertainty analysis and the dashboard.

---

_Private repository. Code © the team. CRM data © project, not included._
