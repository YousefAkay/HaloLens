"""Streamlit app: seven tabs and a sidebar over the aggregates JSON (I-11a shell, I-12 AI layer, I-11b, I-11c redesign).

Owner: INT; the I-11b polish and the I-11c newsprint redesign were delegated to FCT (docs/decisions/FCT.md).

Run locally:  streamlit run app/streamlit_app.py
Demo mode (default) reads outputs/public/aggregates_synthetic.json. Real mode reads outputs/private/aggregates.json,
which exists only after the real export (gitignored). Every file is validated against contracts.AGGREGATES_SCHEMA and must
carry the mode that was selected. The sidebar holds the language, the data mode, Reload and the notes; the tabs are 01 Answer,
02 Why, 03 Validation, 04 Scenario Lab, 05 Buildings, 06 Questions, 07 Sources (`?view=<tab>` opens one directly). The Claude API
is called only through app/narrative.py, and only with aggregates, counts-only notes and the question. Without a key the app runs
on the levers and, in synthetic mode, validated preset answers.
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

from app import narrative
from app.ui import DEFAULT_LANG, LANGS, t
from app.ui import components as ui
from app.ui.components import backtest_frame, rule_summary, selection_ranking  # noqa: F401  (re-exported for tests)
from app.ui.theme import inject_css
from leaselens.config import load_config, repo_root
from leaselens.contracts import AGGREGATES_SCHEMA
from leaselens.evaluate.backtest import RULE_DEC31

MISSING = ui.MISSING  # shown when the aggregates hold null (not computable)
TAB_KEYS = ("answer", "why", "validation", "lab", "buildings", "ask", "sources")
VIEWS = tuple(t(f"tab_{key}", "en") for key in TAB_KEYS)  # English tab names, in order
VIEW_PARAMETER = "view"  # ?view=<tab key> opens that tab (used for the screenshots)
MODE_DEMO, MODE_REAL = "Demo (synthetic)", "Real (outputs/private)"
MODE_OF = {MODE_DEMO: "synthetic", MODE_REAL: "real"}  # the document's own mode must match the selected one
LEVER_CHOICES = ("minus", "zero", "plus")
MET_CHOICES = ("exempt", "guideline")
LEVER_DEFAULTS = {"lever_incentive": "zero", "lever_renewal": "zero", "lever_met": "exempt", "lever_rule": "jan31"}
NO_KEY_REASONS = ("cache_synthetic_only", "cache_missing", "cache_rejected")
NO_KEY_MESSAGES = {reason: t(f"no_key_{reason}", "en") for reason in NO_KEY_REASONS}
HIDDEN_ANSWER_REASONS = {"cache_synthetic_only", "cache_rejected"}  # a cached text is never shown for these
PILL_COLUMNS = 3  # preset question pills per row
MODE_LABEL = {MODE_DEMO: "mode_demo", MODE_REAL: "mode_real"}  # label keys of the data-mode control (the values stay MODE_*)
LANG_SHORT = {"en": "EN", "fr": "FR"}  # compact labels of the language control
LANGUAGE_LABEL = "Langue / Language"  # bilingual on purpose: it is shown before a language is chosen


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
    """One Claude client per session, or None without a key (the app then runs on levers and preset answers)."""
    return narrative.get_client()


@st.cache_data
def _notes() -> list[str]:
    return narrative.committed_notes()


def pct(value: float | None, decimals: int = ui.PERCENT_DECIMALS) -> str:
    return ui.pct(value, decimals)


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def _plain(text: str) -> None:
    """A quiet paragraph (no box): used for notices, empty states and unavailable answers."""
    _html(f'<p class="ll-plain">{ui.esc(text)}</p>')


# ---------------------------------------------------------------------------
# 01 Answer, 02 Why
# ---------------------------------------------------------------------------
def overview(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> None:
    """Tab 01: the caption, the headline number, its range and four supporting facts (visible without scrolling)."""
    _html(ui.hero(doc, lang) + ui.stats(doc, lang))


def why(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> None:
    _html(ui.section_header("why", t("why_kicker", lang), t("why_headline", lang)) + ui.steps(lang))
    measured, limits = st.columns(2)
    with measured:
        st.markdown(f"**{t('why_measured_title', lang)}**")
        st.markdown(t("why_measured_body", lang))
    with limits:
        st.markdown(f"**{t('why_limits_title', lang)}**")
        st.markdown(t("why_limits_body", lang))
    with st.expander(t("why_definition", lang)):
        st.write(doc["definition"])


# ---------------------------------------------------------------------------
# 03 Validation
# ---------------------------------------------------------------------------
def validation(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> None:
    cfg = _config()
    figures = ui.validation_figures(doc, cfg)
    headline_model = doc["headline"]["model"]
    shown_model = ui.model_name(doc)
    _html(ui.section_header("validation", t("val_kicker", lang), ui.validation_headline(figures, lang)))
    if figures["champion"] is not None and headline_model is not None and figures["champion"] != headline_model:
        st.warning(t("val_mismatch", lang, ranked=figures["champion"], headline=headline_model))
    left, right = st.columns(2)
    with left:
        st.markdown(f"**{t('val_left_title', lang, model=shown_model)}**")
        if figures["left"]:
            _html(ui.forecast_actual(figures["left"], lang))
        else:
            _plain(t("val_empty", lang))
        st.caption(t("val_left_caption", lang))
    with right:
        st.markdown(f"**{t('val_right_title', lang)}**")
        if figures["models"]:
            _html(ui.mae_chart(figures["models"], lang))
            st.caption(t("val_right_caption", lang, selection=", ".join(map(str, figures["selection_years"])),
                         holdout=figures["holdout_year"]))
            st.caption(t("val_weak", lang, n=len(figures["selection_years"])))
        else:
            _plain(t("val_empty", lang))
    with st.expander(t("val_table", lang)):
        st.dataframe(pd.DataFrame(doc["backtest"]).round(ui.ERROR_DECIMALS), hide_index=True)
    strict = rule_summary(doc, cfg, RULE_DEC31)
    pooled = rule_summary(doc, cfg, "jan31")
    names = {"model": t("val_col_model", lang), "mae_selection_pp": t("val_col_selection", lang),
             "mae_holdout_pp": t("val_col_holdout", lang), "mae_all_pp": t("val_col_pooled", lang),
             "n_folds_run": t("val_col_folds", lang)}
    with st.expander(t("val_strict", lang, strict=ui.format_date(doc["as_of"]["external_strict_cutoff"], lang))):
        if strict.empty:
            _plain(t("val_empty", lang))
        else:
            st.dataframe(strict[["model", "mae_selection_pp", "mae_holdout_pp"]].rename(columns=names).round(ui.ERROR_DECIMALS),
                         hide_index=True)
    with st.expander(t("val_pooled", lang)):
        st.dataframe(pooled[["model", "mae_all_pp"]].rename(columns=names).round(ui.ERROR_DECIMALS), hide_index=True)


# ---------------------------------------------------------------------------
# 04 Scenario Lab
# ---------------------------------------------------------------------------
def _reset_levers() -> None:
    """Callback of the reset link: the four levers go back to the baseline."""
    for key, value in LEVER_DEFAULTS.items():
        st.session_state[key] = value


def _lever(key: str, label: str, options: tuple[str, ...] | list[str], labeller, lang: str) -> str:
    """One segmented lever with its label and a magenta 'changed' word when it is off the baseline."""
    default = LEVER_DEFAULTS[key]
    st.session_state.setdefault(key, default)  # initialised here, not with `default=`, because the reset link also writes it
    changed = f'<span class="ll-changed">{ui.esc(t("lab_changed", lang))}</span>' \
        if (st.session_state.get(key) or default) != default else ""
    _html(f'<div class="ll-lab-label">{ui.esc(label)}{changed}</div>')
    value = st.segmented_control(label, list(options), key=key, format_func=labeller, label_visibility="collapsed")
    return value or default  # clicking the active segment deselects it: fall back to the baseline


def _call_copilot(question: str, doc: dict[str, Any], client: Any, selection: dict[str, str]) -> dict[str, Any]:
    """Ask the copilot; pass the on-screen selection when scenario_copilot accepts one."""
    options: dict[str, Any] = {"rule": selection["rule"]}
    if "selection" in inspect.signature(narrative.scenario_copilot).parameters:
        options["selection"] = selection
    # TODO(I-12b): scenario_copilot has no `selection` parameter yet; once it has, the lines above pass the lever choices.
    return narrative.scenario_copilot(question, doc, client, **options)


def _safe(call, *args: Any) -> tuple[Any, bool]:
    """(result, failed): a provider failure (timeout, network, anything) never reaches the page as a traceback."""
    try:
        return call(*args), False
    except Exception:  # noqa: BLE001 - any provider failure becomes a short calm message
        return None, True


def _understood(row: dict[str, Any] | None, lang: str) -> None:
    """The scenario the AI selected, as small pills."""
    if not row:
        return
    items = []
    for field, label_key, prefix in (("incentive_shift", "lab_incentive", "opt_incentive_"),
                                     ("renewal_shift", "lab_renewal", "opt_renewal_"), ("met_regime", "lab_met", "opt_met_")):
        value = row.get(field)
        if value in LEVER_CHOICES + MET_CHOICES:
            items.append(f"{t(label_key, lang)}: {t(prefix + value, lang)}")
    if items:
        _html(f'<div class="ll-small">{ui.esc(t("lab_understood", lang))}</div>' + ui.chips_html(items))


def _no_key_message(reason: str | None, lang: str) -> str:
    return t(f"no_key_{reason}", lang) if reason in NO_KEY_REASONS else t("no_key_generic", lang)


def _render_copilot(answer: dict[str, Any] | None, failed: bool, lang: str) -> None:
    """The copilot's own text (it already uses the matching baseline); never rebuilt from the levers."""
    if failed or answer is None:
        _plain(t("ask_error", lang))
        return
    status, text = answer.get("status"), answer.get("text")
    if text and status in {"ai", "fallback"}:
        _html(f'<p class="ll-plain" style="color:var(--ink)">{ui.esc(text)}</p>')
    elif status == "no_key":
        _plain(_no_key_message(answer.get("reason"), lang))
    else:
        _plain(t("lab_use_levers", lang))
    _understood(answer.get("selection") or answer.get("row"), lang)


@st.fragment
def _lab(doc: dict[str, Any], lang: str) -> None:
    """The four levers and their result; a fragment, so moving a lever does not rerun (or jump) the whole page."""
    client = _client()
    controls, result = st.columns([2, 3], gap="large")
    as_of = doc["as_of"]
    rule_labels = {"jan31": ui.format_date(as_of["external_cutoff"], lang),
                   "dec31_strict": t("opt_rule_strict", lang, day=ui.format_day_month(as_of["external_strict_cutoff"], lang))}
    with controls:
        incentive = _lever("lever_incentive", t("lab_incentive", lang), LEVER_CHOICES,
                           lambda value: t(f"opt_incentive_{value}", lang), lang)
        renewal = _lever("lever_renewal", t("lab_renewal", lang), LEVER_CHOICES,
                         lambda value: t(f"opt_renewal_{value}", lang), lang)
        met = _lever("lever_met", t("lab_met", lang), MET_CHOICES, lambda value: t(f"opt_met_{value}", lang), lang)
        rule = _lever("lever_rule", t("lab_rule", lang), list(narrative.INFORMATION_RULES),
                      lambda value: rule_labels.get(value, value), lang)
        st.button(t("lab_reset", lang), key="reset_lab", on_click=_reset_levers)
    row = narrative.scenario_row(doc, incentive, renewal, met, rule)
    base = narrative.baseline_row(doc, rule)
    selection = {"incentive": incentive, "renewal": renewal, "met": met, "rule": rule}
    with result:
        numbers = None if row is None or base is None else (
            row["headline_net_pct"], row["headline_contract_pct"], base["headline_net_pct"])
        if numbers is None or not all(ui.present(value) for value in numbers):
            _plain(t("lab_no_row", lang))  # a missing grid row or a null figure: say so, compute and word nothing
        else:
            scenarios = doc["scenarios"]
            low, high = ui.scale_with([row["headline_net_pct"], base["headline_net_pct"], row["headline_contract_pct"],
                                       scenarios["low_net_pct"], scenarios["high_net_pct"]], *ui.HERO_SCALE)
            delta = f"{row['headline_net_pct'] - base['headline_net_pct']:+.{ui.ERROR_DECIMALS}f} {t('lab_pp', lang)}"
            _html('<div class="ll-big-row">'
                  f'<div><div class="ll-num-cap">{ui.esc(t("lab_baseline", lang))}</div>'
                  f'<div class="ll-base-num">{ui.esc(pct(base["headline_net_pct"]))}</div></div>'
                  f'<div><div class="ll-num-cap">{ui.esc(t("lab_scenario", lang))}</div>'
                  f'<div class="ll-scn-num">{ui.esc(pct(row["headline_net_pct"]))}</div></div>'
                  f'<div class="ll-delta">{ui.esc(t("lab_delta", lang, delta=delta))}</div></div>'
                  + ui.range_bar(low, high, band=(scenarios["low_net_pct"], scenarios["high_net_pct"]),
                                 markers=((row["headline_contract_pct"], "contract"),),
                                 dots=((base["headline_net_pct"], "base"), (row["headline_net_pct"], "scenario")),
                                 band_class="lab")
                  + f'<div class="ll-small">{ui.esc(t("lab_envelope", lang))}</div>')
            st.write(narrative.fallback_scenario_text(row, base, lang))
        if client is not None:
            question = st.text_input(t("lab_copilot_question", lang), key="copilot_question")
            if question and st.button(t("lab_explain", lang), key="copilot_go"):
                answer, failed = _safe(_call_copilot, question, doc, client, selection)
                _render_copilot(answer, failed, lang)


def scenarios_sources(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> None:
    """Section 04: the levers and their result, then what moves the forecast most (the sources sit in the footer)."""
    _html(ui.section_header("lab", t("lab_kicker", lang), t("lab_headline", lang)))
    _lab(doc, lang)
    rows = ui.tornado_rows(doc, lang)
    if rows:
        st.markdown(f"**{t('tornado_title', lang)}**")
        _html(ui.tornado(rows))
        st.caption(t("tornado_caption", lang))


# ---------------------------------------------------------------------------
# 05 Buildings
# ---------------------------------------------------------------------------
def building_view(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> None:
    cells = ui.building_cells(doc, lang)
    _html(ui.section_header("buildings", t("bd_kicker", lang), ui.building_headline(cells, lang)))
    if cells is None:
        st.info(t("bd_empty", lang))
        return
    _html(ui.building_dots(cells, lang))
    st.caption(t("bd_caption", lang))
    with st.expander(t("bd_table", lang)):
        table = cells[["label", "n_pairs", "net_pct_shrunk", "net_pct_raw", "contract_pct_shrunk"]].rename(columns={
            "label": t("bd_col_cell", lang), "n_pairs": t("bd_col_pairs", lang), "net_pct_shrunk": t("bd_col_net", lang),
            "net_pct_raw": t("bd_col_raw", lang), "contract_pct_shrunk": t("bd_col_contract", lang)})
        st.dataframe(table.round(ui.ERROR_DECIMALS), hide_index=True)


# ---------------------------------------------------------------------------
# 06 Ask the analysis
# ---------------------------------------------------------------------------
def _render_answer(question: str, result: dict[str, Any] | None, failed: bool, lang: str) -> None:
    """Every status of ask_analysis, calmly: a rejected or unavailable answer is never shown."""
    if failed or result is None:
        _plain(t("ask_error", lang))
        return
    status, text, reason = result.get("status"), result.get("text"), result.get("reason")
    if status == "ai" and text:
        _html(ui.answer_html(question, text, lang, checked=True))
    elif status == "refused":
        _plain(text or t("ask_refused", lang))
    elif status == "no_key":
        if text and reason not in HIDDEN_ANSWER_REASONS:  # a cached answer already passed the number guard
            _html(ui.answer_html(question, text, lang, checked=True))
        else:
            _plain(_no_key_message(reason, lang))
    elif status == "fallback":
        _plain(text or t("ask_fallback", lang))
    else:  # "unavailable" or anything unknown
        _plain(_no_key_message(reason, lang) if reason else t("ask_unavailable", lang))


def _pills(lang: str) -> list[str]:
    return list(narrative.PRESET_QUESTIONS) + [t("example_occupancy", lang)]


def ask_analysis_view(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> None:
    client = _client()
    _html(ui.section_header("ask", t("ask_kicker", lang), t("ask_headline", lang), ai=True))
    if client is None:
        _plain(t("ask_no_key_demo", lang) if doc.get("mode") == "synthetic" else t("no_key_cache_synthetic_only", lang))
    clicked = None
    questions = _pills(lang)
    with st.container(key="pills"):
        for start in range(0, len(questions), PILL_COLUMNS):
            for offset, column in enumerate(st.columns(PILL_COLUMNS)):
                index = start + offset
                if index < len(questions) and column.button(questions[index], key=f"pill_{index}"):
                    clicked = questions[index]
                    st.session_state["preset"] = clicked
    free = st.text_input(t("ask_free", lang), key="free_question")
    answer_clicked = st.button(t("ask_answer", lang), key="answer_go")
    chosen = clicked or free or st.session_state.get("preset", "")
    if chosen and (clicked or answer_clicked):
        with st.spinner(t("ask_spinner", lang)):
            result, failed = _safe(narrative.ask_analysis, chosen, doc, _notes(), client)
        _render_answer(chosen, result, failed, lang)


# ---------------------------------------------------------------------------
# 07 Sources, sidebar and page
# ---------------------------------------------------------------------------
def sources_view(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> None:
    """Tab 07: the public series behind the forecast, with their release dates."""
    sources = pd.DataFrame(doc["sources"])
    _html(ui.section_header("sources", t("src_kicker", lang), t("src_headline", lang)))
    st.markdown(f"**{t('foot_sources', lang, n=len(sources))}**")
    if not sources.empty:
        link = t("foot_col_url", lang)
        table = sources[["series_id", "publisher", "release_date", "url"]].rename(columns={
            "series_id": t("foot_col_series", lang), "publisher": t("foot_col_publisher", lang),
            "release_date": t("foot_col_release", lang), "url": link})
        st.dataframe(table, hide_index=True, column_config={link: st.column_config.LinkColumn(link)})


def sidebar() -> tuple[str, str]:
    """Language, data mode, Reload, the reading note, the API-key note and the trust notes; returns (language, data mode)."""
    lang = st.session_state.get("lang") or DEFAULT_LANG  # the radios below set these keys before the next run
    with st.sidebar:
        st.radio(LANGUAGE_LABEL, list(LANGS), key="lang", horizontal=True, format_func=LANG_SHORT.get)
        st.radio(t("data_label", lang), [MODE_DEMO, MODE_REAL], key="data_mode", horizontal=True,
                 format_func=lambda value: t(MODE_LABEL[value], lang))
        if st.button(t("foot_reload", lang), key="reload"):
            st.cache_data.clear()
        with st.expander(t("side_how_title", lang)):
            st.write(t("side_how_body", lang))
        st.caption(t("foot_key_note", lang))
        with st.expander(t("foot_trust", lang)):
            for key in ("trust_privacy", "trust_ai", "trust_guard", "trust_tools", "trust_font"):
                st.markdown(t(key, lang))
    return st.session_state["lang"], st.session_state["data_mode"]


def main() -> None:
    st.set_page_config(page_title="Halo Lens", layout="wide", initial_sidebar_state="expanded")
    inject_css()
    st.session_state.setdefault("lang", DEFAULT_LANG)  # initialised here, not with `default=`, so tests and callbacks can set them
    st.session_state.setdefault("data_mode", MODE_DEMO)
    lang, mode = sidebar()
    _html(ui.masthead_title(mode == MODE_REAL, lang))
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
    _html(ui.notice(doc))
    labels = [t(f"tab_{key}", lang) for key in TAB_KEYS]
    requested = st.query_params.get(VIEW_PARAMETER)
    default = labels[TAB_KEYS.index(requested)] if requested in TAB_KEYS else None
    renderers = (overview, why, validation, scenarios_sources, building_view, ask_analysis_view, sources_view)
    for tab, render in zip(st.tabs(labels, default=default), renderers):
        with tab:
            render(doc, lang)


if __name__ == "__main__":  # Streamlit runs the script as __main__; importing the module (tests) must not render it
    main()
