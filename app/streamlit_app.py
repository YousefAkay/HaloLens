"""Streamlit app: six tabs over the aggregates JSON (I-11a shell, I-12 AI layer, I-11b polish).

Owner: INT; the I-11b polish (theme, FR/EN, charts, validation, audit fixes) was delegated to FCT (docs/decisions/FCT.md).

Run locally:  streamlit run app/streamlit_app.py
Demo mode (default) reads outputs/public/aggregates_synthetic.json. Real mode reads outputs/private/aggregates.json,
which exists only after the real export (gitignored). Every file is validated against contracts.AGGREGATES_SCHEMA and must
carry the mode that was selected. The tabs are Overview, Validation, Scenarios, By building, Ask the analysis, Trust. The
Claude API is called only through app/narrative.py, and only with aggregates, counts-only notes and the question. Without a
key the app runs on the dropdowns and, in synthetic mode, validated preset answers. `?view=<tab>` opens one tab directly.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from typing import Any

# `streamlit run app/streamlit_app.py` puts app/ on the import path, not the repository root, so `from app import ...` needs it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st
from jsonschema import Draft202012Validator, FormatChecker

from app import charts, narrative
from app.ui import DEFAULT_LANG, LANG_NAMES, LANGS, chips, header, inject_css, kpi_card, t, trust_panel
from leaselens.config import load_config, repo_root
from leaselens.contracts import AGGREGATES_SCHEMA, COLOR_NET
from leaselens.evaluate.backtest import RULE_DEC31, RULE_JAN31, select_champion, summarize_models

DISPLAY_DECIMALS = 1  # headline and companion percentages
ERROR_DECIMALS = 2  # backtest errors, in percentage points
MISSING = "n/a"  # shown when the aggregates hold null (not computable)
TAB_KEYS = ("overview", "validation", "scenarios", "building", "ask", "trust")
VIEWS = tuple(t(f"tab_{key}", "en") for key in TAB_KEYS)  # English tab labels (the default language)
MODE_DEMO, MODE_REAL = "Demo (synthetic)", "Real (outputs/private)"
MODE_OF = {MODE_DEMO: "synthetic", MODE_REAL: "real"}  # the document's own mode must match the selected one
LANGUAGE_LABEL = "Language / Langue"  # bilingual on purpose: it is shown before a language is chosen
VIEW_PARAMETER = "view"
LEVER_CHOICES = ("minus", "zero", "plus")
MET_CHOICES = ("exempt", "guideline")
NO_KEY_REASONS = ("cache_synthetic_only", "cache_missing", "cache_rejected")
NO_KEY_MESSAGES = {reason: t(f"no_key_{reason}", "en") for reason in NO_KEY_REASONS}
HIDDEN_ANSWER_REASONS = {"cache_synthetic_only", "cache_rejected"}  # a cached text is never shown for these
EXAMPLE_COUNT = 4  # clickable example questions: three preset ones and the occupancy guardrail
HIGHLIGHT_ALPHA = 0.18  # opacity of the champion row's tint


def _tint(hex_colour: str, alpha: float) -> str:
    """A translucent version of a contracts colour (CSS rgba), so the highlight stays inside the shared palette."""
    red, green, blue = (int(hex_colour[index:index + 2], 16) for index in (1, 3, 5))
    return f"rgba({red}, {green}, {blue}, {alpha})"


HIGHLIGHT_STYLE = f"font-weight: bold; background-color: {_tint(COLOR_NET, HIGHLIGHT_ALPHA)}"  # champion row


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
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


@st.cache_data
def _cached_load(path: str, modified_ns: int, size: int) -> dict[str, Any]:
    """The cache key holds the file's modification time and size, so an edited file is read again."""
    return load_aggregates(Path(path))


def _load(mode: str) -> dict[str, Any]:
    path = real_path() if mode == MODE_REAL else synthetic_path()
    status = path.stat()  # FileNotFoundError when the real export has not run
    return _cached_load(str(path), status.st_mtime_ns, status.st_size)


@st.cache_resource
def _config() -> dict[str, Any]:
    """Configuration for the selection years and the champion metric (no data path is read from it here)."""
    return load_config(mode="synthetic")


@st.cache_resource
def _client() -> Any | None:
    """One Claude client per session, or None without a key (the app then runs on dropdowns and preset answers)."""
    return narrative.get_client()


@st.cache_data
def _notes() -> list[str]:
    return narrative.committed_notes()


def pct(value: float | None, decimals: int = DISPLAY_DECIMALS) -> str:
    return MISSING if value is None else f"{value:.{decimals}f} %"


def _pp(value: float | None, lang: str) -> str:
    return MISSING if value is None else f"{value:+.{DISPLAY_DECIMALS}f} {t('pp', lang)}"


def _rule_label(rule: str, lang: str) -> str:
    return t(f"rule_{rule}", lang)


# ---------------------------------------------------------------------------
# Validation tables (the ranking that chose the champion comes from the pipeline's own rule)
# ---------------------------------------------------------------------------
def backtest_frame(doc: dict[str, Any]) -> pd.DataFrame:
    """The backtest rows in the shape select_champion and summarize_models expect (model, year, rule, abs error)."""
    rows = pd.DataFrame(doc["backtest"]).rename(columns={"information_rule": "rule"})
    rows["abs_error_pp_net"] = rows["error_pp_net"].abs()
    return rows


def selection_ranking(doc: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """The pre-declared champion rule applied to the file's backtest rows, so the displayed ranking is the pipeline's own.

    Returns select_champion's dict (champion, ranking, selection_years, holdout_year, ...). Raises ValueError when no model
    has a forecast for every selection year.
    """
    return select_champion(backtest_frame(doc), cfg)


def rule_summary(doc: dict[str, Any], cfg: dict[str, Any], rule: str) -> pd.DataFrame:
    """Selection, holdout and pooled mean absolute net error per model for one information rule."""
    summary = summarize_models(backtest_frame(doc), cfg)
    return summary[summary["rule"] == rule].drop(columns="rule").reset_index(drop=True)


def _model_table(frame: pd.DataFrame, lang: str, champion: str | None = None) -> Any:
    """A per-model error table with localized headers; the champion row is highlighted."""
    names = {"model": t("val_col_model", lang), "mae_selection_pp": t("val_col_selection", lang),
             "mae_holdout_pp": t("val_col_holdout", lang),
             "mae_all_pp": f"{t('val_col_pooled', lang)} ({t('val_pooled_note', lang)})",
             "n_folds_run": t("val_col_folds", lang)}
    table = frame.rename(columns=names)
    model_column = names["model"]

    def highlight(row: pd.Series) -> list[str]:
        return [HIGHLIGHT_STYLE if champion and row[model_column] == champion else ""] * len(row)

    return table.style.apply(highlight, axis=1).format(precision=ERROR_DECIMALS)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
def overview(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> None:
    if doc["mode"] == "synthetic":
        st.warning(doc["note"])
    headline, companions, scenarios = doc["headline"], doc["companions"], doc["scenarios"]
    net, contract = headline["net_pct"], headline["contract_pct"]
    effect = None if net is None or contract is None else contract - net
    rule = _rule_label(headline["information_rule"], lang)
    columns = st.columns(4)
    with columns[0]:
        kpi_card(t("kpi_net", lang), pct(net), t("kpi_net_caption", lang), "net")
    with columns[1]:
        kpi_card(t("kpi_contract", lang), pct(contract), t("kpi_contract_caption", lang), "contract")
    with columns[2]:
        kpi_card(t("kpi_effect", lang), _pp(effect, lang), t("kpi_effect_caption", lang), "effect")
    with columns[3]:
        kpi_card(t("kpi_champion", lang), headline["model"], t("kpi_champion_caption", lang, rule=rule), "champion")
    st.caption(t("medians_line", lang, net=pct(companions["median_net_pct"]), contract=pct(companions["median_contract_pct"])))
    st.subheader(t("overview_answer", lang))
    answer = charts.answer_chart(doc, lang)
    if answer is not None:
        st.altair_chart(answer, width="stretch")
        st.caption(f"{t('chart_band', lang)} · {t('chart_e2', lang)}")
    st.subheader(t("overview_provinces", lang))
    for column, code in zip(st.columns(2), ("QC", "ON")):
        province = headline["provinces"][code]
        with column, st.container(border=True):
            st.markdown(f"**{t('province_' + code.lower(), lang)}**")
            if province["net_pct"] is None and province["contract_pct"] is None:
                st.write(t("province_unavailable", lang))
            else:
                st.write(t("province_card", lang, net=pct(province["net_pct"]), contract=pct(province["contract_pct"])))
    st.subheader(t("reading_title", lang))
    facts = {"model": headline["model"], "rule": rule, "net": pct(net), "contract": pct(contract), "year": doc["target_year"]}
    if effect is not None and scenarios["low_net_pct"] is not None and scenarios["high_net_pct"] is not None:
        st.write(t("reading", lang, effect=f"{effect:.{DISPLAY_DECIMALS}f}", low=pct(scenarios["low_net_pct"]),
                   high=pct(scenarios["high_net_pct"]), **facts))
    else:
        st.write(t("reading_no_range", lang, **facts))
    coverage = doc["coverage"]
    st.subheader(t("coverage_title", lang))
    st.write(t("coverage_line", lang, leases=coverage["leases"], units=coverage["units"], eligible=coverage["eligible_pairs"],
               excluded=coverage["excluded_pairs"], segments=coverage["segments"]))
    st.subheader(t("definition_title", lang))
    st.write(doc["definition"])


def validation(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> None:
    cfg = _config()
    champion = doc["headline"]["model"]
    st.subheader(t("val_selection_title", lang))
    st.caption(t("val_selection_caption", lang))
    try:
        chosen = selection_ranking(doc, cfg)
    except ValueError:
        st.info(t("val_empty", lang))
        chosen = None
    if chosen is not None:
        if chosen["champion"] != champion:
            st.warning(t("val_mismatch", lang, ranked=chosen["champion"], headline=champion))
        ranking = chosen["ranking"][["model", "mae_selection_pp", "n_selection_folds_run"]].rename(
            columns={"n_selection_folds_run": "n_folds_run"})
        st.dataframe(_model_table(ranking, lang, champion=chosen["champion"]), hide_index=True)
        st.info(t("val_weak", lang))
        st.subheader(t("val_holdout_title", lang))
        st.dataframe(_model_table(chosen["ranking"][["model", "mae_holdout_pp"]], lang, champion=chosen["champion"]),
                     hide_index=True)
    st.subheader(t("val_strict_title", lang))
    strict = rule_summary(doc, cfg, RULE_DEC31)
    if strict.empty:
        st.info(t("val_empty", lang))
    else:
        st.dataframe(_model_table(strict[["model", "mae_selection_pp", "mae_holdout_pp"]], lang), hide_index=True)
    pooled = rule_summary(doc, cfg, RULE_JAN31)
    if not pooled.empty:
        st.subheader(f"{t('val_pooled_title', lang)} ({t('val_pooled_note', lang)})")
        st.dataframe(_model_table(pooled[["model", "mae_all_pp"]], lang), hide_index=True)
    rule = st.radio(t("val_rule_toggle", lang), (RULE_JAN31, RULE_DEC31), key="val_rule", horizontal=True,
                    format_func=lambda value: t(f"val_rule_{value}", lang))
    chart = charts.backtest_chart(doc, rule, lang)
    if chart is None:
        st.info(t("val_empty", lang))
    else:
        st.altair_chart(chart)


def scenarios_view(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> None:
    scenarios = doc["scenarios"]
    st.subheader(t("sc_title", lang))
    low, central, high = st.columns(3)
    low.metric(t("sc_low", lang), pct(scenarios["low_net_pct"]))
    central.metric(t("sc_central", lang), pct(scenarios["central_net_pct"]))
    high.metric(t("sc_high", lang), pct(scenarios["high_net_pct"]))
    st.caption(t("sc_caption", lang))
    tornado = charts.tornado_chart(doc, lang)
    if tornado is not None:
        st.subheader(t("sc_tornado", lang))
        st.altair_chart(tornado, width="stretch")
        st.caption(t("sc_tornado_caption", lang))
    band = charts.bootstrap_band(doc, lang)
    if band is not None:
        st.subheader(t("sc_bootstrap", lang))
        st.altair_chart(band, width="stretch")
        st.caption(t("sc_bootstrap_caption", lang))


def building_view(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> None:
    st.subheader(t("bd_title", lang))
    cells = charts.building_cells(doc, lang)
    if cells is None:
        st.info(t("bd_empty", lang))
        return
    st.caption(t("bd_caption", lang))
    table = cells[["label", "n_pairs", "net_pct_shrunk", "net_pct_raw", "contract_pct_shrunk"]].rename(columns={
        "label": t("bd_col_cell", lang), "n_pairs": t("bd_col_pairs", lang), "net_pct_shrunk": t("bd_col_net", lang),
        "net_pct_raw": t("bd_col_raw", lang), "contract_pct_shrunk": t("bd_col_contract", lang)})
    st.dataframe(table.round(ERROR_DECIMALS), hide_index=True)
    chart = charts.building_chart(doc, lang)
    if chart is not None:
        st.altair_chart(chart, width="stretch")


# ---------------------------------------------------------------------------
# Ask the analysis
# ---------------------------------------------------------------------------
def _safe(call, *args: Any) -> tuple[Any, bool]:
    """(result, failed): a provider failure (timeout, network, anything) never reaches the page as a traceback."""
    try:
        return call(*args), False
    except Exception:  # noqa: BLE001 - any provider failure becomes a short calm message
        return None, True


def _call_copilot(question: str, doc: dict[str, Any], client: Any, selection: dict[str, str]) -> dict[str, Any]:
    """Ask the copilot; pass the on-screen selection when scenario_copilot accepts one."""
    options: dict[str, Any] = {"rule": selection["rule"]}
    if "selection" in inspect.signature(narrative.scenario_copilot).parameters:
        options["selection"] = selection
    # TODO(I-12b): scenario_copilot has no `selection` parameter yet; once it has, the lines above pass the dropdown choices.
    return narrative.scenario_copilot(question, doc, client, **options)


def _understood_chips(row: dict[str, Any] | None, lang: str) -> None:
    """Show the scenario the AI selected, as small pills."""
    if not row:
        return
    items = []
    for field, label_key, prefix in (("incentive_shift", "ask_incentive", "lever_"), ("renewal_shift", "ask_renewal", "lever_"),
                                     ("met_regime", "ask_met", "met_")):
        value = row.get(field)
        if value in LEVER_CHOICES + MET_CHOICES:
            items.append(f"{t(label_key, lang)}: {t(prefix + value, lang)}")
    if row.get("information_rule") in narrative.INFORMATION_RULES:
        items.append(f"{t('ask_rule', lang)}: {_rule_label(row['information_rule'], lang)}")
    if items:
        st.markdown(f"**{t('ask_understood', lang)}**")
        chips(items)


def _no_key_message(reason: str | None, lang: str) -> str:
    return t(f"no_key_{reason}", lang) if reason in NO_KEY_REASONS else t("no_key_generic", lang)


def _render_copilot(answer: dict[str, Any] | None, failed: bool, lang: str) -> None:
    """The copilot's own text (it already uses the matching baseline); never rebuilt from the dropdowns."""
    if failed or answer is None:
        st.warning(t("ask_error", lang))
        return
    status, text = answer.get("status"), answer.get("text")
    if text and status in {"ai", "fallback"}:
        st.write(text)
    elif status == "no_key":
        st.info(_no_key_message(answer.get("reason"), lang))
    else:
        st.info(t("ask_use_dropdowns", lang))
    _understood_chips(answer.get("selection") or answer.get("row"), lang)


def _render_answer(result: dict[str, Any] | None, failed: bool, lang: str) -> None:
    """Every status of ask_analysis, calmly: a rejected or unavailable answer is never shown."""
    if failed or result is None:
        st.warning(t("ask_error", lang))
        return
    status, text, reason = result.get("status"), result.get("text"), result.get("reason")
    if status == "ai" and text:
        st.write(text)
    elif status == "refused":
        st.info(text or t("ask_refused", lang))
    elif status == "no_key":
        if text and reason not in HIDDEN_ANSWER_REASONS:
            st.write(text)
        else:
            st.info(_no_key_message(reason, lang))
    elif status == "fallback":
        st.info(text or t("ask_fallback", lang))
    else:  # "unavailable" or anything unknown
        st.info(_no_key_message(reason, lang) if reason else t("ask_unavailable", lang))


def _examples(lang: str) -> list[str]:
    return list(narrative.PRESET_QUESTIONS[:EXAMPLE_COUNT - 1]) + [t("example_occupancy", lang)]


def _no_key_banner(doc: dict[str, Any], lang: str) -> str:
    return t("ask_no_key_demo", lang) if doc.get("mode") == "synthetic" else t("no_key_cache_synthetic_only", lang)


def ask_analysis_view(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> None:
    client = _client()
    st.markdown(f"**{t('ask_ai_line', lang)}**")
    if client is None:
        st.info(_no_key_banner(doc, lang))
    st.subheader(t("ask_scenarios", lang))
    incentive = st.selectbox(t("ask_incentive", lang), LEVER_CHOICES, index=1, key="lever_incentive",
                             format_func=lambda value: t(f"lever_{value}", lang))
    renewal = st.selectbox(t("ask_renewal", lang), LEVER_CHOICES, index=1, key="lever_renewal",
                           format_func=lambda value: t(f"lever_{value}", lang))
    met = st.selectbox(t("ask_met", lang), MET_CHOICES, index=0, key="lever_met",
                       format_func=lambda value: t(f"met_{value}", lang))
    rule = st.selectbox(t("ask_rule", lang), list(narrative.INFORMATION_RULES), index=0, key="lever_rule",
                        format_func=lambda value: _rule_label(value, lang))
    row = narrative.scenario_row(doc, incentive, renewal, met, rule)
    base = narrative.baseline_row(doc, rule)
    if row is not None:
        st.write(narrative.fallback_scenario_text(row, base, lang))
    selection = {"incentive": incentive, "renewal": renewal, "met": met, "rule": rule}
    question = st.text_input(t("ask_copilot_question", lang), key="copilot_question")
    if question and client is not None and st.button(t("ask_copilot_go", lang), key="copilot_go"):
        answer, failed = _safe(_call_copilot, question, doc, client, selection)
        _render_copilot(answer, failed, lang)
    st.subheader(t("ask_qa_title", lang))
    st.caption(t("ask_examples", lang))
    clicked = None
    for index, (column, example) in enumerate(zip(st.columns(EXAMPLE_COUNT), _examples(lang))):
        if column.button(example, key=f"example_{index}"):
            clicked = example
    preset = st.selectbox(t("ask_preset", lang), ["-"] + list(narrative.PRESET_QUESTIONS), key="preset")
    free = st.text_input(t("ask_free", lang), key="free_question")
    chosen = clicked or free or (preset if preset != "-" else "")
    answer_clicked = st.button(t("ask_answer", lang), key="answer_go")
    if chosen and (clicked or answer_clicked):
        result, failed = _safe(narrative.ask_analysis, chosen, doc, _notes(), client)
        _render_answer(result, failed, lang)


# ---------------------------------------------------------------------------
# Trust
# ---------------------------------------------------------------------------
def trust_view(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> None:
    st.subheader(t("trust_sources", lang))
    sources = pd.DataFrame(doc["sources"])
    if not sources.empty:
        link = t("trust_col_url", lang)
        sources = sources[["series_id", "publisher", "release_date", "url"]].rename(columns={
            "series_id": t("trust_col_series", lang), "publisher": t("trust_col_publisher", lang),
            "release_date": t("trust_col_release", lang), "url": link})
        st.dataframe(sources, hide_index=True, column_config={link: st.column_config.LinkColumn(link)})
    trust_panel(doc, lang)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Halo Lens", layout="wide")
    inject_css()
    lang = st.sidebar.radio(LANGUAGE_LABEL, LANGS, index=LANGS.index(DEFAULT_LANG), key="lang", horizontal=True,
                            format_func=LANG_NAMES.get)
    mode = st.sidebar.radio(t("sidebar_data", lang), [MODE_DEMO, MODE_REAL], key="data_mode")
    if st.sidebar.button(t("sidebar_reload", lang), key="reload"):
        st.cache_data.clear()
    with st.sidebar.expander(t("sidebar_how_title", lang)):
        st.write(t("sidebar_how_body", lang))
    st.sidebar.caption(t("sidebar_key_note", lang))
    try:
        doc = _load(mode)
    except FileNotFoundError:
        st.error(t("no_real", lang))
        st.stop()
    except Exception as error:  # a non-conforming file stops the app with a clear message
        st.error(t("bad_file", lang, error=type(error).__name__))
        st.stop()
    if doc["mode"] != MODE_OF[mode]:
        st.error(t("mode_mismatch", lang, found=doc["mode"], expected=MODE_OF[mode]))
        st.stop()
    header(doc, lang)
    views = (overview, validation, scenarios_view, building_view, ask_analysis_view, trust_view)
    labels = [t(f"tab_{key}", lang) for key in TAB_KEYS]
    requested = st.query_params.get(VIEW_PARAMETER)
    default = labels[TAB_KEYS.index(requested)] if requested in TAB_KEYS else None
    for tab, view in zip(st.tabs(labels, default=default), views):
        with tab:
            view(doc, lang)


if __name__ == "__main__":  # Streamlit runs the script as __main__; importing the module (tests) must not render it
    main()
