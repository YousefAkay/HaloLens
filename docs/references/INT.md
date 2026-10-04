# References INT

Append one bullet per entry, newest last. Format: title, author or publisher, URL, how it was used.

## Sponsor material
- **`template.ipynb`** and **the challenge brief (`instructions`)**, project ( 2026, Défi « Clés en main »), supplied in the sponsor package, not redistributed here. Used for the column reading conventions, the loading cells, the method hints and the `estimate_2026` / `backtest` signatures. The notebook is derived from the starter.

## Software documentation
- **jupytext**, documentation, https://jupytext.readthedocs.io/ — percent-format section files assembled into the notebook (`scripts/build_notebook.py`).
- **nbclient**, Jupyter project, https://nbclient.readthedocs.io/ — executes the notebook on a clean kernel for the build and for the jury simulation.
- **Streamlit**, documentation, https://docs.streamlit.io/ — the dashboard (`app/streamlit_app.py`) and its headless `AppTest` tests.
- **jsonschema**, documentation, https://python-jsonschema.readthedocs.io/ — validates the aggregates file against `contracts.AGGREGATES_SCHEMA`.
- **pandas**, documentation, https://pandas.pydata.org/docs/ — all table handling.
- **matplotlib**, documentation, https://matplotlib.org/stable/ — every figure in the notebook and the dashboard.

## AI tool documentation
- **Claude API documentation (tool use, structured outputs)**, Anthropic, https://docs.anthropic.com/ — the scenario copilot (one enum-restricted tool that selects a precomputed row) and the Q&A over the aggregates (`app/narrative.py`).

## Our own design
- **Privacy wall and number guard**, LeaseLens team, `AGENTS.md` §3 and §15, `app/number_guard.py`, `app/narrative.py` — the Claude API receives only public pages, the aggregates file, committed notes with real-data numbers removed, and the question; every generated number must appear in the aggregates or the text is replaced by a deterministic fallback.
