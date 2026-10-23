# AGENTS.md: contributor guide for Halo Lens

Halo Lens (Python package `halolens`) estimates the next-year rent increase of a residential portfolio from lease
history and public market data. It defines the increase precisely, compares each unit with itself, handles
incentives explicitly, separates renewals from turnovers under each province's rules, and validates the method by
backtest. Humans and coding agents follow the same rules.

## Architecture (`src/halolens/`)

- `io/`: loading with SHA-256 checks, the data dictionary (source names to canonical names), QA report.
- `measure/`: same-unit lease pairs, composition bridge, renewals vs turnovers.
- `market/`: public sources registry (with release dates), asking-rent signal, regulation matrix.
- `incentives/`: incentive engine, concession-to-lease matching.
- `forecast/`: as-of snapshots, baselines, monthly index, nowcast, engine combination, scenarios.
- `evaluate/`: backtests, metrics, unit-cluster bootstrap.
- `export/`: aggregate export (no unit-level data) for the app.
- `contracts.py`: canonical column names, table schemas, dataclasses. Change it deliberately and update all users.
- `notebook/sections/`: jupytext "percent" files assembled by `scripts/build_notebook.py`. `app/`: Streamlit dashboard.

## Conventions

- Configuration lives in `config/*.yaml`, read through `halolens.config.load_config()`. No magic numbers: every
  threshold, date, window, weight, seed and scenario lever is a documented YAML key. Each key lives in one file.
- Pure functions: take tables and config, return new tables. Only `io/` reads files. Type hints and docstrings.
- Match units on `prop_code + unit_code` (or `unit_id`), never on a site name plus unit code.
- Leakage rule: a forecast for year y uses only information available at its cutoff (training data, thresholds,
  weights and public data are all restricted to what was knowable then). A test appends fake future rows and checks
  that the forecast does not change.
- Never quote occupancy, vacancy, absorption or total rent roll from a lease extract; it cannot measure them.
- Python 3.11+. New dependencies need a clear reason. Seeds come from config. Every exclusion is counted and reported.
- Notebook sections start with a Markdown cell (input, operation, rationale, checks); numbers in text come from code.

## Privacy

- Never commit user data. CSV files are only allowed in `data/public/` and `data/synthetic/`; `data/private/`,
  `outputs/private/`, `models/` and `.env` are gitignored and blocked by pre-commit hooks.
- Tests run on the synthetic fixtures in `data/synthetic/`. Never print or display raw rows of real tables; show
  counts, shapes and aggregates only.
- External APIs only receive public pages or aggregate JSON, never row-level data.
- Leak scanner: `python scripts/leak_scan.py` checks the tree and git history against a private denylist kept in
  `outputs/private/leak_denylist.yaml` (start from `config/leak_denylist.example.yaml`). It prints counts and paths only.
- Secrets go in `.env` (`ANTHROPIC_API_KEY`); every AI feature must work without a key through deterministic fallbacks.

## Commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pre-commit install
pytest -q                                          # unit tests on synthetic data
python scripts/build_notebook.py --synthetic       # build and execute the notebook
python scripts/export_aggregates.py --synthetic    # aggregates for the app
streamlit run app/streamlit_app.py                 # dashboard (synthetic demo by default)
python scripts/leak_scan.py --tree-only            # privacy scan of tracked files
```

Before a pull request: `pre-commit run --all-files` and `pytest -q` pass. Keep changes small and described by tests.
