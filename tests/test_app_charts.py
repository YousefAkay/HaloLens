"""Tests for the polished app (I-11b): charts, labels, tabs in both languages, reload, mode check, AI statuses. Owner: FCT.

Everything runs headlessly on the synthetic aggregates file (Streamlit's AppTest). No browser, no network, no CRM data.
"""

from __future__ import annotations

import copy
import json
import pathlib
import time

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app import charts, narrative, streamlit_app
from app.ui import DEFAULT_LANG, LABELS, LANGS, t
from leaselens.config import load_config, repo_root
from leaselens.contracts import COLOR_NET
from leaselens.evaluate.backtest import select_champion

APP = repo_root() / "app" / "streamlit_app.py"
TIMEOUT_SECONDS = 90
SYNTHETIC = json.loads(streamlit_app.synthetic_path().read_text(encoding="utf-8"))
CHART_BUILDERS = {
    "answer": lambda doc, lang: charts.answer_chart(doc, lang),
    "backtest": lambda doc, lang: charts.backtest_chart(doc, "jan31", lang),
    "tornado": lambda doc, lang: charts.tornado_chart(doc, lang),
    "building": lambda doc, lang: charts.building_chart(doc, lang),
}
OPTIONAL_KEYS = {"answer": [("headline", None)], "backtest": [("backtest", [])], "tornado": [("sensitivity", [])],
                 "building": [("building_beds", [])]}


def _main():
    from app.streamlit_app import main

    main()


def new_app(monkeypatch, client=None) -> AppTest:
    """The whole page, run through the imported module so that monkeypatched paths and clients take effect."""
    monkeypatch.setattr(narrative, "get_client", lambda: client)
    return AppTest.from_function(_main, default_timeout=TIMEOUT_SECONDS)


def switch_language(at: AppTest, lang: str) -> AppTest:
    at.sidebar.radio(key="lang").set_value(lang)
    return at.run()


def all_text(at: AppTest) -> str:
    parts = [element.value for element in list(at.markdown) + list(at.info) + list(at.warning) + list(at.error)
             + list(at.caption) + list(at.subheader)]
    return "\n".join(str(part) for part in parts)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("name", list(CHART_BUILDERS))
def test_every_chart_builds_from_the_synthetic_json(name, lang):
    chart = CHART_BUILDERS[name](SYNTHETIC, lang)
    assert chart is not None
    assert chart.to_dict()                                  # a valid Vega-Lite specification


def test_the_bootstrap_band_is_absent_without_the_optional_key_and_builds_with_it():
    assert charts.bootstrap_band(SYNTHETIC, "en") is None
    document = copy.deepcopy(SYNTHETIC)
    document["bootstrap"] = {"net_pct": {"lower": 3.0, "upper": 5.0}, "contract_pct": {"lower": 5.0, "upper": 6.0}}
    assert charts.bootstrap_band(document, "en").to_dict()
    document["bootstrap"] = {"net_pct": {"lower": None, "upper": None}}
    assert charts.bootstrap_band(document, "en") is None


@pytest.mark.parametrize("name", list(OPTIONAL_KEYS))
def test_a_chart_returns_none_when_its_data_is_missing(name):
    for key, empty in OPTIONAL_KEYS[name]:
        document = copy.deepcopy(SYNTHETIC)
        if key == "headline":
            document["headline"]["net_pct"] = empty
        else:
            document[key] = empty
        assert CHART_BUILDERS[name](document, "en") is None


def test_the_answer_chart_drops_the_scenario_layers_when_the_range_is_null():
    document = copy.deepcopy(SYNTHETIC)
    full = len(charts.answer_chart(document, "en").to_dict()["layer"])
    document["scenarios"] = {"low_net_pct": None, "central_net_pct": None, "high_net_pct": None}
    assert len(charts.answer_chart(document, "en").to_dict()["layer"]) == full - 2


def test_the_backtest_chart_follows_the_chosen_rule_and_stars_the_champion():
    specification = charts.backtest_chart(SYNTHETIC, "dec31_strict", "en").to_dict()
    panels = {row["panel"] for row in specification["datasets"][next(iter(specification["datasets"]))]}
    assert any(panel.startswith("★") and SYNTHETIC["headline"]["model"] in panel for panel in panels)
    assert len(panels) == len({row["model"] for row in SYNTHETIC["backtest"]})


def test_every_tornado_bar_has_its_own_label():
    specification = charts.tornado_chart(SYNTHETIC, "en").to_dict()
    rows = specification["datasets"][next(iter(specification["datasets"]))]
    labels = [row["label"] for row in rows]
    assert len(labels) == len(set(labels))                                    # equal labels would draw two rows as one bar


def test_the_tornado_is_sorted_by_absolute_change():
    specification = charts.tornado_chart(SYNTHETIC, "en").to_dict()
    bars = specification["layer"][0]
    order = bars["encoding"]["y"]["sort"]
    rows = specification["datasets"][next(iter(specification["datasets"]))]
    deltas = {row["label"]: abs(row["delta_pp"]) for row in rows}
    assert [deltas[label] for label in order] == sorted(deltas.values(), reverse=True)


def test_chart_colours_come_from_the_contracts_module():
    from leaselens.contracts import COLOR_CONTRACT, COLOR_MARKET, COLOR_NAIVE
    allowed = {COLOR_NET, COLOR_CONTRACT, COLOR_MARKET, COLOR_NAIVE, "black"}
    for name, builder in CHART_BUILDERS.items():
        text = json.dumps(builder(SYNTHETIC, "en").to_dict())
        for token in set(__import__("re").findall(r"#[0-9A-Fa-f]{6}", text)):
            assert token in allowed, (name, token)


# ---------------------------------------------------------------------------
# Labels and theme
# ---------------------------------------------------------------------------
def test_french_and_english_labels_have_identical_keys():
    assert set(LABELS["fr"]) == set(LABELS["en"])
    assert all(isinstance(text, str) and text for language in LABELS.values() for text in language.values())


def test_every_placeholder_is_the_same_in_both_languages():
    import string
    for key in LABELS["en"]:
        fields = {language: {name for _, name, _, _ in string.Formatter().parse(LABELS[language][key]) if name}
                  for language in LANGS}
        assert fields["en"] == fields["fr"], key


def test_the_theme_primary_colour_is_the_net_colour():
    text = (repo_root() / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert f'primaryColor = "{COLOR_NET}"' in text


def test_tab_labels_follow_the_language(monkeypatch):
    at = new_app(monkeypatch).run()
    assert [tab.label for tab in at.tabs] == [t(f"tab_{key}", "en") for key in streamlit_app.TAB_KEYS]
    switch_language(at, "fr")
    assert [tab.label for tab in at.tabs] == [t(f"tab_{key}", "fr") for key in streamlit_app.TAB_KEYS]


# ---------------------------------------------------------------------------
# Every tab, both languages
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("lang", LANGS)
def test_every_tab_runs_without_exceptions(monkeypatch, lang):
    at = new_app(monkeypatch).run()
    switch_language(at, lang)
    assert not at.exception
    assert len(at.tabs) == len(streamlit_app.TAB_KEYS)
    text = all_text(at)
    assert t("kpi_net", lang) in {metric.label for metric in at.metric}
    assert t("val_weak", lang) in text and t("trust_privacy", lang) in text and t("sc_caption", lang) in text


@pytest.mark.parametrize("lang", LANGS)
def test_deep_links_open_each_tab_without_exceptions(monkeypatch, lang):
    for key in streamlit_app.TAB_KEYS:
        at = new_app(monkeypatch)
        at.query_params["view"] = key
        at.run()
        switch_language(at, lang)
        assert not at.exception, key


def test_provinces_show_not_available_when_the_value_is_null(monkeypatch, tmp_path):
    document = copy.deepcopy(SYNTHETIC)
    for code in ("QC", "ON"):
        document["headline"]["provinces"][code] = {"net_pct": None, "contract_pct": None}
    path = tmp_path / "aggregates.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(streamlit_app, "synthetic_path", lambda: path)
    at = new_app(monkeypatch).run()
    assert not at.exception
    assert sum(t("province_unavailable", "en") in element.value for element in at.markdown) == 2


def test_kpi_values_come_from_the_json(monkeypatch):
    at = new_app(monkeypatch).run()
    values = {metric.label: metric.value for metric in at.metric}
    headline = SYNTHETIC["headline"]
    assert values[t("kpi_net", "en")] == f"{headline['net_pct']:.1f} %"
    assert values[t("kpi_contract", "en")] == f"{headline['contract_pct']:.1f} %"
    assert values[t("kpi_effect", "en")] == f"{headline['contract_pct'] - headline['net_pct']:+.1f} pp"
    assert values[t("kpi_champion", "en")] == headline["model"]


# ---------------------------------------------------------------------------
# Loading: cache key, reload, mode check
# ---------------------------------------------------------------------------
def test_an_edited_file_is_read_again_and_reload_works(monkeypatch, tmp_path):
    path = tmp_path / "aggregates.json"
    path.write_text(json.dumps(SYNTHETIC), encoding="utf-8")
    monkeypatch.setattr(streamlit_app, "synthetic_path", lambda: path)
    at = new_app(monkeypatch).run()
    before = {metric.label: metric.value for metric in at.metric}[t("kpi_net", "en")]
    edited = copy.deepcopy(SYNTHETIC)
    edited["headline"]["net_pct"] = 12.3456
    time.sleep(0.01)
    path.write_text(json.dumps(edited), encoding="utf-8")
    at.run()                                                                   # a plain rerun already sees the new file
    assert {metric.label: metric.value for metric in at.metric}[t("kpi_net", "en")] == "12.3 %" != before
    at.sidebar.button(key="reload").click().run()
    assert not at.exception
    assert {metric.label: metric.value for metric in at.metric}[t("kpi_net", "en")] == "12.3 %"


def test_the_cache_key_includes_modification_time_and_size():
    parameters = list(streamlit_app._cached_load.__wrapped__.__code__.co_varnames[:3])
    assert parameters == ["path", "modified_ns", "size"]


@pytest.mark.parametrize("lang", LANGS)
def test_a_document_whose_mode_does_not_match_the_selection_is_rejected(monkeypatch, tmp_path, lang):
    document = copy.deepcopy(SYNTHETIC)
    document["mode"] = "real"                                                  # the demo selection expects a synthetic file
    path = tmp_path / "aggregates.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(streamlit_app, "synthetic_path", lambda: path)
    at = new_app(monkeypatch).run()
    switch_language(at, lang)
    assert not at.exception
    assert any(t("mode_mismatch", lang, found="real", expected="synthetic") == error.value for error in at.error)
    assert not at.metric                                                       # nothing from the mismatched file is shown


def test_the_sidebar_says_that_a_key_change_needs_a_restart(monkeypatch):
    at = new_app(monkeypatch).run()
    assert any(t("sidebar_key_note", "en") in element.value for element in at.sidebar.caption)


# ---------------------------------------------------------------------------
# Validation: the ranking is the pipeline's own
# ---------------------------------------------------------------------------
def test_the_displayed_selection_ranking_picks_the_pipelines_champion():
    cfg = load_config(mode="synthetic")
    chosen = streamlit_app.selection_ranking(SYNTHETIC, cfg)
    table = pd.DataFrame(SYNTHETIC["backtest"]).rename(columns={"information_rule": "rule"})
    table["abs_error_pp_net"] = table["error_pp_net"].abs()
    assert chosen["champion"] == select_champion(table, cfg)["champion"]
    assert chosen["champion"] == SYNTHETIC["headline"]["model"]


def test_the_ranking_uses_only_the_selection_years_and_keeps_the_holdout_apart():
    cfg = load_config(mode="synthetic")
    chosen = streamlit_app.selection_ranking(SYNTHETIC, cfg)
    frame = streamlit_app.backtest_frame(SYNTHETIC)
    jan31 = frame[frame["rule"] == "jan31"]
    model = chosen["ranking"].iloc[0]["model"]
    expected = jan31[(jan31["model"] == model) & jan31["year"].isin(cfg["forecast_years"]["selection_years"])][
        "abs_error_pp_net"].mean()
    assert chosen["ranking"].iloc[0]["mae_selection_pp"] == pytest.approx(expected)
    holdout = jan31[(jan31["model"] == model) & (jan31["year"] == cfg["forecast_years"]["holdout_year"])]["abs_error_pp_net"]
    assert chosen["ranking"].iloc[0]["mae_holdout_pp"] == pytest.approx(holdout.iloc[0])


def test_the_validation_tab_labels_the_pooled_average_as_descriptive_and_warns_on_a_mismatch(monkeypatch, tmp_path):
    at = new_app(monkeypatch).run()
    text = all_text(at)
    assert t("val_pooled_note", "en") in text and t("val_strict_title", "en") in text
    assert t("val_holdout_title", "en") in text
    assert not any("picks" in warning.value for warning in at.warning)
    document = copy.deepcopy(SYNTHETIC)
    document["headline"]["model"] = "B1_trailing_mean" if SYNTHETIC["headline"]["model"] != "B1_trailing_mean" else "B0_last_year"
    path = tmp_path / "aggregates.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(streamlit_app, "synthetic_path", lambda: path)
    mismatch = new_app(monkeypatch).run()
    assert any("picks" in warning.value for warning in mismatch.warning)


# ---------------------------------------------------------------------------
# By building
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("lang", LANGS)
def test_duplicate_building_names_get_distinct_public_labels(lang):
    cells = charts.building_cells(SYNTHETIC, lang)
    assert cells["label"].is_unique
    document = copy.deepcopy(SYNTHETIC)
    document["building_beds"] = [
        {"building": "North Court", "beds": 1, "n_pairs": 12, "net_pct_raw": 3.0, "net_pct_shrunk": 3.0,
         "contract_pct_raw": 3.0, "contract_pct_shrunk": 3.0},
        {"building": "North Court", "beds": 2, "n_pairs": 8, "net_pct_raw": 3.1, "net_pct_shrunk": 3.1,
         "contract_pct_raw": 3.1, "contract_pct_shrunk": 3.1},
        {"building": "North Court", "beds": 1, "n_pairs": 21, "net_pct_raw": 3.2, "net_pct_shrunk": 3.2,
         "contract_pct_raw": 3.2, "contract_pct_shrunk": 3.2},
        {"building": "Cedar Park", "beds": 1, "n_pairs": 7, "net_pct_raw": 3.3, "net_pct_shrunk": 3.3,
         "contract_pct_raw": 3.3, "contract_pct_shrunk": 3.3}]
    labelled = charts.building_cells(document, lang)
    assert labelled["label"].is_unique and len(labelled) == 4
    north = labelled[labelled["building"] == "North Court"]
    assert sorted(north["phase"]) == [1, 1, 2]
    assert all(t("bd_phase", lang, phase=phase) in label for phase, label in zip(north["phase"], north["label"]))
    cedar = labelled[labelled["building"] == "Cedar Park"]["label"].iloc[0]
    assert "phase" not in cedar.lower() and "phase" not in LABELS[lang]["bd_cell"]


def test_the_building_table_and_chart_show_the_same_cells(monkeypatch):
    cells = charts.building_cells(SYNTHETIC, "en")
    specification = charts.building_chart(SYNTHETIC, "en").to_dict()
    chart_labels = {row["label"] for row in specification["datasets"][next(iter(specification["datasets"]))]}
    assert chart_labels == set(cells["label"])
    at = new_app(monkeypatch).run()
    shown = {label for frame in at.dataframe for label in frame.value.get(t("bd_col_cell", "en"), [])}
    assert shown == set(cells["label"])
    assert "n_pairs" in json.dumps(specification)                              # pair counts reach the tooltip


def test_no_property_code_or_unit_identifier_reaches_the_building_labels():
    for lang in LANGS:
        labels = " ".join(charts.building_cells(SYNTHETIC, lang)["label"])
        for forbidden in ("prop_code", "unit_id", "unit_code"):
            assert forbidden not in labels


# ---------------------------------------------------------------------------
# Ask the analysis: every status, calmly
# ---------------------------------------------------------------------------
def _qa_view(document, lang):
    from app.streamlit_app import ask_analysis_view

    ask_analysis_view(document, lang)


def qa_app(monkeypatch, copilot=None, ask=None, key=True, lang="en") -> AppTest:
    monkeypatch.setattr(streamlit_app, "_client", lambda: object() if key else None)
    monkeypatch.setattr(streamlit_app, "_notes", lambda: [])
    if copilot is not None:
        monkeypatch.setattr(narrative, "scenario_copilot", copilot)
    if ask is not None:
        monkeypatch.setattr(narrative, "ask_analysis", ask)
    return AppTest.from_function(_qa_view, args=(SYNTHETIC, lang), default_timeout=TIMEOUT_SECONDS).run()


def ask_question(at: AppTest, question: str = "Quelle est la hausse ?") -> AppTest:
    at.text_input(key="free_question").input(question).run()
    return at.button(key="answer_go").click().run()


ROW = narrative.scenario_row(SYNTHETIC, "plus", "zero", "guideline", "dec31_strict")   # a full grid row, as the copilot returns


@pytest.mark.parametrize("answer, shown, hidden", [
    ({"status": "ai", "text": "AI TEXT 4.9 %"}, "AI TEXT 4.9 %", None),
    ({"status": "fallback", "text": "GUARDED TEXT"}, "GUARDED TEXT", None),
    ({"status": "refused", "text": "REFUSED TEXT"}, "REFUSED TEXT", None),
    ({"status": "no_key", "text": "CACHED OK"}, "CACHED OK", None),
    ({"status": "no_key", "text": "REJECTED SYNTHETIC 99.9 %", "reason": "cache_rejected"},
     t("no_key_cache_rejected", "en"), "REJECTED SYNTHETIC"),
    ({"status": "no_key", "text": None, "reason": "cache_synthetic_only"}, t("no_key_cache_synthetic_only", "en"), None),
    ({"status": "no_key", "text": None, "reason": "cache_missing"}, t("no_key_cache_missing", "en"), None),
    ({"status": "no_key", "text": None, "reason": "something_new"}, t("no_key_generic", "en"), None),
    ({"status": "unavailable", "text": None}, t("ask_unavailable", "en"), None),
    ({"status": "unavailable", "text": None, "reason": "privacy"}, t("no_key_generic", "en"), None),
    ({"status": "fallback", "text": None}, t("ask_fallback", "en"), None),
    ({"status": "surprise", "text": "UNKNOWN STATUS TEXT"}, t("ask_unavailable", "en"), "UNKNOWN STATUS TEXT"),
])
def test_every_qa_status_renders_calmly(monkeypatch, answer, shown, hidden):
    at = ask_question(qa_app(monkeypatch, ask=lambda *args, **kwargs: answer))
    assert not at.exception
    assert shown in all_text(at)
    if hidden:
        assert hidden not in all_text(at)


@pytest.mark.parametrize("failure", [TimeoutError("provider timed out"), ConnectionError("network down"), RuntimeError("boom")])
def test_a_provider_failure_shows_a_short_message_and_keeps_the_dropdowns(monkeypatch, failure):
    def failing(*args, **kwargs):
        raise failure

    at = ask_question(qa_app(monkeypatch, ask=failing))
    assert not at.exception
    assert t("ask_error", "en") in all_text(at)
    assert "Traceback" not in all_text(at) and str(failure) not in all_text(at)
    assert at.selectbox(key="lever_incentive").value == "zero"
    at.text_input(key="copilot_question").input("explain").run()
    broken = qa_app(monkeypatch, copilot=failing)
    broken.text_input(key="copilot_question").input("explain").run()
    broken.button(key="copilot_go").click().run()
    assert not broken.exception and t("ask_error", "en") in all_text(broken)
    assert broken.selectbox(key="lever_rule").value == "jan31"


def test_the_copilot_text_is_shown_as_returned_and_the_scenario_it_chose_appears_as_chips(monkeypatch):
    answer = {"status": "ai", "text": "COPILOT TEXT", "row": ROW}
    at = qa_app(monkeypatch, copilot=lambda question, doc, client, rule="jan31": answer)
    at.text_input(key="copilot_question").input("what if incentives rise").run()
    at.button(key="copilot_go").click().run()
    assert not at.exception
    text = all_text(at)
    assert "COPILOT TEXT" in text and t("ask_understood", "en") in text
    chips_html = " ".join(element.value for element in at.markdown if "ll-chip" in element.value)
    for expected in (t("lever_plus", "en"), t("met_guideline", "en"), t("rule_dec31_strict", "en")):
        assert expected in chips_html


def test_a_fallback_copilot_text_is_not_rebuilt_from_the_dropdown_rule(monkeypatch):
    """The copilot's text already uses the baseline of the rule it chose; the app must not substitute the dropdown's."""
    answer = {"status": "fallback", "text": "TEXT BUILT BY THE COPILOT", "row": ROW}
    at = qa_app(monkeypatch, copilot=lambda question, doc, client, rule="jan31": answer)
    at.selectbox(key="lever_rule").select("jan31").run()
    at.text_input(key="copilot_question").input("scenario").run()
    at.button(key="copilot_go").click().run()
    assert "TEXT BUILT BY THE COPILOT" in all_text(at)
    assert not any(narrative.fallback_scenario_text(ROW, narrative.baseline_row(SYNTHETIC, "jan31"), "en") == element.value
                   for element in at.markdown)


def test_the_selection_is_passed_to_the_copilot_when_it_accepts_one(monkeypatch):
    seen = {}

    def copilot(question, doc, client, rule="jan31", selection=None):
        seen.update(rule=rule, selection=selection)
        return {"status": "ai", "text": "ok", "row": ROW}

    at = qa_app(monkeypatch, copilot=copilot)
    at.selectbox(key="lever_incentive").select("plus").run()
    at.selectbox(key="lever_met").select("guideline").run()
    at.text_input(key="copilot_question").input("q").run()
    at.button(key="copilot_go").click().run()
    assert seen["selection"] == {"incentive": "plus", "renewal": "zero", "met": "guideline", "rule": "jan31"}


def test_the_copilot_still_works_when_it_has_no_selection_parameter(monkeypatch):
    seen = {}

    def copilot(question, doc, client, rule="jan31"):
        seen["rule"] = rule
        return {"status": "ai", "text": "ok", "row": ROW}

    at = qa_app(monkeypatch, copilot=copilot)
    at.text_input(key="copilot_question").input("q").run()
    at.button(key="copilot_go").click().run()
    assert not at.exception and seen["rule"] == "jan31"


@pytest.mark.parametrize("lang", LANGS)
def test_four_clickable_examples_including_the_occupancy_guardrail(monkeypatch, lang):
    at = qa_app(monkeypatch, key=False, lang=lang)
    assert [button.key for button in at.button if str(button.key).startswith("example_")] == [f"example_{i}" for i in range(4)]
    at.button(key="example_3").click().run()
    assert not at.exception
    assert narrative.REFUSAL[narrative.detect_language(t("example_occupancy", lang))] in all_text(at)


def test_a_preset_example_gets_its_cached_answer_in_the_demo_without_a_key(monkeypatch):
    question = narrative.PRESET_QUESTIONS[0]
    monkeypatch.setattr(narrative, "load_preset_cache", lambda: {})
    at = qa_app(monkeypatch, key=False)
    at.button(key="example_0").click().run()
    assert not at.exception and t("no_key_cache_missing", "en") in all_text(at)
    assert question in [button.label for button in at.button]


# ---------------------------------------------------------------------------
# Privacy: what the app reads
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["ui.py", "charts.py", "streamlit_app.py"])
def test_the_app_files_name_no_crm_path_and_no_network_library(name):
    source = (repo_root() / "app" / name).read_text(encoding="utf-8")
    assert "data/private" not in source
    for forbidden in ("requests", "httpx", "urllib", "import anthropic", "read_csv", ".csv"):
        assert forbidden not in source, (name, forbidden)


def test_a_demo_session_reads_no_csv_and_no_crm_path(monkeypatch):
    read = []
    original = pathlib.Path.read_text
    monkeypatch.setattr(pathlib.Path, "read_text", lambda self, *args, **kwargs: (read.append(str(self)),
                                                                                  original(self, *args, **kwargs))[1])
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: pytest.fail("the app must not read CSV files"))
    at = new_app(monkeypatch).run()
    switch_language(at, "fr")
    assert not at.exception
    assert read and not any("data/private" in path or path.endswith(".csv") for path in read)
    assert all("outputs/private" not in path for path in read)                 # demo mode never touches the private folder


def test_default_language_is_one_named_constant():
    assert DEFAULT_LANG in LANGS


def test_the_script_runs_from_outside_the_repository_without_a_pythonpath(tmp_path):
    """`streamlit run app/streamlit_app.py` must find the app package itself (it once failed with ModuleNotFoundError)."""
    import os
    import subprocess
    import sys

    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    completed = subprocess.run([sys.executable, str(APP)], cwd=tmp_path, env=environment, capture_output=True, text=True,
                               timeout=TIMEOUT_SECONDS)
    assert "ModuleNotFoundError" not in completed.stderr, completed.stderr[-400:]
    assert completed.returncode == 0, completed.stderr[-400:]
