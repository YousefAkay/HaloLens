"""Streamlit app shell with four views that read only the aggregates JSON. Task I-11a.

Owner: INT.

Run locally:  streamlit run app/streamlit_app.py
The app reads outputs/public/aggregates_synthetic.json (synthetic demo mode), validates it against
contracts.AGGREGATES_SCHEMA, and renders four views: Overview, Why, Validation, Scenarios & Sources.
It never reads CRM data and makes no network calls, so it runs offline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from jsonschema import Draft202012Validator, FormatChecker

from leaselens.config import load_config, repo_root
from leaselens.contracts import AGGREGATES_SCHEMA

DISPLAY_DECIMALS = 1  # headline and companion percentages
ERROR_DECIMALS = 2  # backtest errors, in percentage points
MISSING = "n/a"  # shown when the aggregates hold null (not computable)
VIEWS = ("Overview", "Why", "Validation", "Scenarios & Sources")


def load_aggregates(path: Path) -> dict[str, Any]:
    """Read and validate an aggregates file. Raises jsonschema.ValidationError if it does not conform."""
    document = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(AGGREGATES_SCHEMA, format_checker=FormatChecker()).validate(document)
    return document


def synthetic_path() -> Path:
    """The only file this app reads: the invented demo aggregates."""
    cfg = load_config(mode="synthetic")
    return repo_root() / cfg["outputs"]["public_dir"] / cfg["outputs"]["aggregates_synthetic_file"]


def pct(value: float | None, decimals: int = DISPLAY_DECIMALS) -> str:
    return MISSING if value is None else f"{value:.{decimals}f} %"


def overview(doc: dict[str, Any]) -> None:
    if doc["mode"] == "synthetic":
        st.warning(doc["note"])
    headline, companions = doc["headline"], doc["companions"]
    st.caption(
        f"Target year {doc['target_year']} · CRM cutoff {doc['as_of']['crm_cutoff']} · "
        f"public data by {doc['as_of']['external_cutoff']} "
        f"(sensitivity: {doc['as_of']['external_strict_cutoff']})"
    )
    left, right = st.columns(2)
    left.metric("Headline, net of incentives", pct(headline["net_pct"]))
    right.metric("Headline, contractual", pct(headline["contract_pct"]))
    left.metric("Median, net", pct(companions["median_net_pct"]))
    right.metric("Median, contractual", pct(companions["median_contract_pct"]))
    coverage = doc["coverage"]
    st.subheader("Coverage")
    st.write(f"Leases: {coverage['leases']} · units: {coverage['units']} · eligible pairs: "
             f"{coverage['eligible_pairs']} · excluded pairs: {coverage['excluded_pairs']} · "
             f"segments: {coverage['segments']}")
    st.subheader("Definition")
    st.write(doc["definition"])


def why(doc: dict[str, Any]) -> None:
    st.subheader("What is measured")
    st.write(doc["definition"])
    st.markdown(
        "- **Same unit:** each unit is compared with its own previous lease, so size, floor and building do not "
        "change the result.\n"
        "- **Fixed composition:** segment weights are frozen at the cutoff, so the mix of leases does not move the "
        "headline.\n"
        "- **Companions are always shown:** the contractual rent and the medians sit beside the headline."
    )
    st.subheader("Limits of this reading")
    st.markdown(
        "- The weights describe observed lease transitions, not occupancy or turnover.\n"
        "- Net rent is adjusted for concessions. It is not cash collected.\n"
        "- Three backtest years support cautious conclusions: scenario ranges, not prediction intervals."
    )


def validation(doc: dict[str, Any]) -> None:
    backtest = pd.DataFrame(doc["backtest"])
    st.subheader("Backtest by year and model")
    st.dataframe(backtest.round(ERROR_DECIMALS), hide_index=True)
    mae = backtest.assign(abs_error=backtest["error_pp_net"].abs()).groupby("model")["abs_error"].mean()
    st.subheader("Mean absolute error, net (percentage points)")
    st.dataframe(mae.round(ERROR_DECIMALS).rename("mean_abs_error_pp").reset_index(), hide_index=True)


def scenarios_sources(doc: dict[str, Any]) -> None:
    scenarios = doc["scenarios"]
    st.subheader("Scenario range, net")
    low, central, high = st.columns(3)
    low.metric("Low", pct(scenarios["low_net_pct"]))
    central.metric("Central", pct(scenarios["central_net_pct"]))
    high.metric("High", pct(scenarios["high_net_pct"]))
    st.caption("Scenarios, not prediction intervals.")
    st.subheader("Sources")
    st.dataframe(pd.DataFrame(doc["sources"]), hide_index=True)


@st.cache_data
def _cached_load(path: str) -> dict[str, Any]:
    return load_aggregates(Path(path))


def main() -> None:
    st.set_page_config(page_title="LeaseLens: 2026 rent increase", layout="wide")
    try:
        doc = _cached_load(str(synthetic_path()))
    except Exception as error:  # a missing or non-conforming file stops the app with a clear message
        st.error(f"Aggregates file not usable: {type(error).__name__}. Check outputs/public.")
        st.stop()
    tabs = st.tabs(list(VIEWS))
    for tab, view in zip(tabs, (overview, why, validation, scenarios_sources)):
        with tab:
            view(doc)


if __name__ == "__main__":  # Streamlit runs the script as __main__; importing the module (tests) must not render it
    main()
