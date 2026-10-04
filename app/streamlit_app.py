"""Streamlit app: six views over the aggregates JSON (I-11a shell, I-12 AI layer).

Owner: INT.

Run locally:  streamlit run app/streamlit_app.py
Demo mode (default) reads outputs/public/aggregates_synthetic.json. Real mode reads outputs/private/aggregates.json,
which exists only after the real export (gitignored). Every file is validated against contracts.AGGREGATES_SCHEMA.
The views are: Overview, Why, Validation, Scenarios & Sources, Ask the analysis, By building. The Claude API is called
only through app/narrative.py, and only with aggregates, counts-only notes and the question. Without a key the app runs
on the dropdowns and the preset answers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from jsonschema import Draft202012Validator, FormatChecker

from app import narrative
from leaselens.config import load_config, repo_root
from leaselens.contracts import AGGREGATES_SCHEMA

DISPLAY_DECIMALS = 1  # headline and companion percentages
ERROR_DECIMALS = 2  # backtest errors, in percentage points
MISSING = "n/a"  # shown when the aggregates hold null (not computable)
VIEWS = ("Overview", "Why", "Validation", "Scenarios & Sources", "Ask the analysis", "By building")
MODE_DEMO, MODE_REAL = "Demo (synthetic)", "Real (outputs/private)"
LEVER_CHOICES = ("minus", "zero", "plus")
MET_CHOICES = ("exempt", "guideline")


def load_aggregates(path: Path) -> dict[str, Any]:
    """Read and validate an aggregates file. Raises jsonschema.ValidationError if it does not conform."""
    document = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(AGGREGATES_SCHEMA, format_checker=FormatChecker()).validate(document)
    return document


def synthetic_path() -> Path:
    """Demo mode: the invented aggregates, committed in outputs/public."""
    cfg = load_config(mode="synthetic")
    return repo_root() / cfg["outputs"]["public_dir"] / cfg["outputs"]["aggregates_synthetic_file"]


def real_path() -> Path:
    """Real mode: the CRM-derived aggregates, written by the real export into the gitignored outputs/private."""
    cfg = load_config(mode="real")
    return repo_root() / cfg["outputs"]["private_dir"] / cfg["outputs"]["aggregates_file"]


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


@st.cache_resource
def _client() -> Any | None:
    """One Claude client per session, or None without a key (the app then runs on dropdowns and preset answers)."""
    return narrative.get_client()


@st.cache_data
def _notes() -> list[str]:
    return narrative.committed_notes()


def ask_analysis_view(doc: dict[str, Any]) -> None:
    client = _client()
    st.markdown("**AI explains, our pipeline computes.**")
    if client is None:
        st.info("No API key in .env: the dropdowns and the preset answers work without it.")
    st.subheader("Scenarios")
    incentive = st.selectbox("Incentive intensity", LEVER_CHOICES, index=1, key="lever_incentive")
    renewal = st.selectbox("Renewal share", LEVER_CHOICES, index=1, key="lever_renewal")
    met = st.selectbox("the Ontario new-build", MET_CHOICES, index=0, key="lever_met")
    rule = st.selectbox("Information rule", list(narrative.INFORMATION_RULES), index=0, key="lever_rule")
    row = narrative.scenario_row(doc, incentive, renewal, met, rule)
    base = narrative.baseline_row(doc, rule)
    if row is not None:
        st.write(narrative.fallback_scenario_text(row, base, "en"))
    question = st.text_input("Ask about a scenario (uses the Claude API when a key is set)", key="copilot_question")
    if question and client is not None and st.button("Explain this scenario", key="copilot_go"):
        answer = narrative.scenario_copilot(question, doc, client, rule=rule)
        if answer["status"] == "ai":
            st.write(answer["text"])
        elif answer["row"] is not None:
            st.write(narrative.fallback_scenario_text(answer["row"], base, narrative.detect_language(question)))
        else:
            st.write("Use the dropdowns above for this question.")
    st.subheader("Questions and answers")
    preset = st.selectbox("Preset questions", ["-"] + list(narrative.PRESET_QUESTIONS), key="preset")
    free = st.text_input("Or ask your own question (sections are cited)", key="free_question")
    chosen = free or (preset if preset != "-" else "")
    if chosen and st.button("Answer", key="answer_go"):
        result = narrative.ask_analysis(chosen, doc, _notes(), client)
        if result["status"] == "no_key":
            st.write(result["text"] or "Preset answers are not cached for this question. Set a key to ask it.")
        else:
            st.write(result["text"])


def building_view(doc: dict[str, Any]) -> None:
    cells = pd.DataFrame(doc["building_beds"])
    st.subheader("Building by bedroom count (E2 engine, shrunk toward the building mean)")
    if cells.empty:
        st.info("No building x bedroom cell reaches the minimum number of pairs.")
        return
    table = cells.sort_values(["building", "beds"]).round(ERROR_DECIMALS)
    st.dataframe(table, hide_index=True)
    ordered = cells.assign(label=cells["building"] + " · " + cells["beds"].astype(str) + " ch.").sort_values(
        "net_pct_shrunk")
    fig, axis = plt.subplots(figsize=(7.5, max(3.0, 0.35 * len(ordered))))
    axis.barh(ordered["label"], ordered["net_pct_shrunk"], color="#E69F00")
    axis.set_xlabel("Net increase, shrunk (%)")
    axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    st.pyplot(fig)


def _load(mode: str) -> dict[str, Any]:
    path = real_path() if mode == MODE_REAL else synthetic_path()
    return _cached_load(str(path))


@st.cache_data
def _cached_load(path: str) -> dict[str, Any]:
    return load_aggregates(Path(path))


def main() -> None:
    st.set_page_config(page_title="LeaseLens: 2026 rent increase", layout="wide")
    mode = st.sidebar.radio("Data", [MODE_DEMO, MODE_REAL], key="data_mode")
    try:
        doc = _load(mode)
    except FileNotFoundError:
        st.error("No real aggregates yet: run scripts/export_aggregates.py --real (the file is gitignored).")
        st.stop()
    except Exception as error:  # a non-conforming file stops the app with a clear message
        st.error(f"Aggregates file not usable: {type(error).__name__}. Check outputs/public or outputs/private.")
        st.stop()
    tabs = st.tabs(list(VIEWS))
    for tab, view in zip(tabs, (overview, why, validation, scenarios_sources, ask_analysis_view, building_view)):
        with tab:
            view(doc)


if __name__ == "__main__":  # Streamlit runs the script as __main__; importing the module (tests) must not render it
    main()
