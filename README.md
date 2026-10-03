# LeaseLens — the portfolio 2026 rent forecast

**project ·  2026 · Défi « Clés en main »**

> **FR —** LeaseLens estime la hausse de loyer 2026 de the portfolio (six immeubles au Québec et en Ontario) à partir de l'historique des baux et de données publiques. Nous définissons précisément la hausse mesurée, comparons chaque unité à elle-même, traitons explicitement les concessions, séparons renouvellements et relocations selon les règles de chaque province, et validons la méthode par backtest sur 2023, 2024 et 2025.

> **EN —** LeaseLens estimates the portfolio's 2026 rent increase from lease history and public market data. We define exactly what "rent increase" means, compare each unit with itself, handle incentives explicitly, separate renewals from turnovers under each province's rules, and validate the method by backtesting 2023, 2024 and 2025.

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
| **2026 headline** | _filled at final build from `aggregates.json`_ |
| Definition | Fixed-composition same-unit growth in rent net of all incentives |
| Contractual companion | _filled at final build_ |
| Scenario range (low / central / high) | _filled at final build_ |
| Forecast as of | 2025-12-31 (no 2026 information used) |
| Backtest error, 2023 / 2024 / 2025 (pp) | _filled at final build_ |

Every figure above is produced by `project_analysis.ipynb`; none is typed by hand.

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
- Python 3.11
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
| Export aggregate results for the app | `python scripts/export_aggregates.py` |
| Launch the dashboard | `streamlit run app/streamlit_app.py` |

The notebook can also be opened directly in Jupyter (`project_analysis.ipynb`) and run top to bottom on a clean kernel.

### Optional: AI features

Two features call the Claude API: extracting public-source values into `data/public/sources_draft.csv`, and writing the dashboard's bilingual evidence card. To enable them, copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. Without a key both features fall back to cached outputs; **the notebook and forecast never need a key.**

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
| Claude (Anthropic), chat | Planning, method design, code review, drafting documentation |
| Claude Code (Anthropic) | Implementing code from reviewed prompts, running tests |
| Claude API (Anthropic) | Extracting values from public web pages into a draft source table, verified by hand; writing the dashboard's bilingual narrative from aggregate results, with an automated check that every number matches the results |

No CRM records were sent to the Claude API. The forecast itself is produced by the documented statistical method, not by an AI model.

## 10. Acknowledgements

Thanks to project for the challenge, data and mentoring. Our notebook builds on the sponsor's `template.ipynb`; reused cells and ideas are credited where they appear. Original contributions: the target definition, the release-date-aware validation framework, the concession reconciliation, the external-data integration, the model comparison, the uncertainty analysis and the dashboard.

---

_Private repository. Code © the team. CRM data © project, not included._
