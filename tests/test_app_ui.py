"""Tests for the newsprint redesign of the app (I-11c): pure components, the single page, levers, answers, privacy. Owner: FCT.

Everything runs headlessly on the synthetic aggregates file (Streamlit's AppTest). No browser, no network, no CRM data.
"""

from __future__ import annotations

import copy
import html
import json
import pathlib
import re
import time

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app import narrative, qa_answers, streamlit_app
from app.ui import DEFAULT_LANG, LABELS, LANGS, t
from app.ui import components as ui
from app.ui import theme
from halolens.config import load_config, repo_root
from halolens.contracts import COLOR_CONTRACT, COLOR_NET
from halolens.evaluate.backtest import select_champion

TIMEOUT_SECONDS = 90
APP = repo_root() / "app" / "streamlit_app.py"
SYNTHETIC = json.loads(streamlit_app.synthetic_path().read_text(encoding="utf-8"))
CFG = load_config(mode="synthetic")
TAB_KEYS = list(streamlit_app.TAB_KEYS)


def _main():
    from app.streamlit_app import main

    main()


def new_app(monkeypatch, client=None, lang="en") -> AppTest:
    """The whole page, run through the imported module so that monkeypatched paths and clients take effect.

    The app opens in French; most tests read English labels, so the language is set explicitly before the first run.
    """
    monkeypatch.setattr(streamlit_app, "_client", lambda: client)   # _client is cached, so patch it rather than get_client
    at = AppTest.from_function(_main, default_timeout=TIMEOUT_SECONDS)
    at.session_state["lang"] = lang
    return at


def ui_notice_text(at: AppTest) -> str:
    return " ".join(element.value for element in at.markdown if "ll-notice" in element.value)


def text_of(at: AppTest) -> str:
    """All visible text of the page: markdown (tags removed, entities decoded), captions, warnings, errors."""
    parts = [element.value for element in list(at.markdown) + list(at.caption) + list(at.warning) + list(at.error)
             + list(at.info)]
    return html.unescape(re.sub(r"<[^>]+>", " ", "\n".join(str(part) for part in parts)))


def number_in(at: AppTest, css_class: str) -> str | None:
    for element in at.markdown:
        found = re.search(rf'class="{css_class}">([^<]+)<', element.value)
        if found:
            return html.unescape(found.group(1))
    return None


def hero_html(at: AppTest) -> str:
    """The hero element (the CSS block names the same classes, so the class attribute is matched)."""
    return next(element.value for element in at.markdown if 'class="ll-hero-number"' in element.value)


def changed_markers(at: AppTest) -> int:
    return sum('<span class="ll-changed">' in element.value for element in at.markdown)


# ---------------------------------------------------------------------------
# Pure components
# ---------------------------------------------------------------------------
def test_hero_shows_the_headline_with_one_decimal_and_escapes_markup():
    document = copy.deepcopy(SYNTHETIC)
    document["headline"]["model"] = "<script>alert(1)</script>"
    markup = ui.hero(document, "en")
    assert f"{document['headline']['net_pct']:.1f}" in markup
    assert "<script>" not in markup and "&lt;script&gt;" in markup


def test_hero_without_a_headline_shows_n_a_and_draws_no_net_marker():
    document = copy.deepcopy(SYNTHETIC)
    document["headline"]["net_pct"] = None
    markup = ui.hero(document, "en")
    assert "n/a" in markup and 'class="ll-marker net"' not in markup
    assert 'class="ll-marker contract"' in markup


def test_hero_band_follows_the_model_range():
    markup = ui.hero(SYNTHETIC, "en")
    low = SYNTHETIC["headline"]["model_range"]["low_net_pct"]
    assert f"left:{100 * low / 8:.2f}%" in markup                           # on the 0 to 8 scale of the design


def test_range_bar_positions_values_in_percent_of_the_scale_and_skips_none():
    markup = ui.range_bar(0.0, 8.0, markers=((4.0, "net"), (None, "contract")), dots=((2.0, "base"),))
    assert "left:50.00%" in markup and "left:25.00%" in markup
    assert "contract" not in markup.split('class="ll-axis"')[0]


def test_scale_widens_instead_of_clipping():
    assert ui.scale_with([1.0, 3.0], 0.0, 8.0) == (0.0, 8.0)
    assert ui.scale_with([1.0, 9.4], 0.0, 8.0) == (0.0, 10.0)
    assert ui.scale_with([-0.5], 0.0, 8.0) == (-1.0, 8.0)
    assert ui.scale_with([None], 0.0, 8.0) == (0.0, 8.0)


def test_dates_are_formatted_from_the_iso_string_in_both_languages():
    assert ui.format_date("2026-01-31", "en") == "31 Jan 2026" and ui.format_date("2026-01-31", "fr") == "31 janv. 2026"
    assert ui.format_day_month("2025-12-31", "en") == "31 Dec"


def test_every_component_escapes_dynamic_text():
    evil = "<b>x</b>"
    assert evil not in ui.section_header("a", evil, evil)
    assert evil not in ui.tornado([{"label": evil, "delta": 1.0}])
    assert evil not in ui.answer_card_html(evil, "headline", evil, [evil], evil, evil, "en")
    assert evil not in ui.chips_html([evil])
    cells = ui.building_cells(SYNTHETIC, "en").assign(label=evil)
    assert evil not in ui.building_dots(cells, "en")


def test_the_stats_use_the_documents_provinces_and_say_not_available_when_null():
    document = copy.deepcopy(SYNTHETIC)
    assert f"{document['headline']['provinces']['QC']['net_pct']:.1f} %" in ui.stats(document, "en")
    document["headline"]["provinces"]["ON"] = {"net_pct": None, "contract_pct": None}
    assert t("stat_province_na", "en") in ui.stats(document, "en")


def test_answer_card_sets_question_heading_lead_bullets_read_more_and_caption():
    markup = ui.answer_card_html("Why?", "headline", "Short answer.", ["one", "two"], "Read more: X.", "Computed from the demo.", "en")
    assert 'class="ll-q">Why?' in markup and 'class="ll-a">Short answer.' in markup
    assert markup.count("<li>") == 2 and "Read more: X." in markup and "Computed from the demo." in markup
    assert t("topic_headline", "en") in markup


def test_tornado_rows_are_sorted_capped_and_skip_zero_and_missing_changes():
    rows = ui.tornado_rows(SYNTHETIC, "en")
    deltas = [abs(row["delta"]) for row in rows]
    assert deltas == sorted(deltas, reverse=True) and len(rows) <= ui.TORNADO_ROWS and all(delta > 0 for delta in deltas)
    document = copy.deepcopy(SYNTHETIC)
    document["sensitivity"] = [{"assumption": "model_choice", "variant": "B1", "setting": "B1", "model": "B1", "delta_pp": 0.0},
                               {"assumption": "model_choice", "variant": "B2", "setting": "B2", "model": "B2", "delta_pp": None}]
    assert ui.tornado_rows(document, "en") == []
    assert len({row["label"] for row in rows}) == len(rows)                  # equal labels would merge two rows


def test_tornado_draws_negative_bars_left_of_the_centre_and_positive_right():
    markup = ui.tornado([{"label": "down", "delta": -1.5}, {"label": "up", "delta": 1.5}])
    assert 'neg" style="left:25.00%;width:25.00%' in markup and 'pos" style="left:50.00%;width:25.00%' in markup


@pytest.mark.parametrize("lang", LANGS)
def test_duplicate_building_names_get_distinct_public_labels(lang):
    assert ui.building_cells(SYNTHETIC, lang)["label"].is_unique
    document = copy.deepcopy(SYNTHETIC)
    cell = {"net_pct_raw": 3.0, "net_pct_shrunk": 3.0, "contract_pct_raw": 3.0, "contract_pct_shrunk": 3.0}
    document["building_beds"] = [{"building": "Building A", "beds": 1, "n_pairs": 12, **cell},
                                 {"building": "Building A", "beds": 2, "n_pairs": 8, **cell},
                                 {"building": "Building A", "beds": 1, "n_pairs": 21, **cell},
                                 {"building": "Building B", "beds": 1, "n_pairs": 7, **cell}]
    cells = ui.building_cells(document, lang)
    assert cells["label"].is_unique and sorted(cells[cells["building"] == "Building A"]["phase"]) == [1, 1, 2]
    assert all("phase" not in label.lower() for label in cells[cells["building"] == "Building B"]["label"])
    for forbidden in ("prop_code", "unit_id", "unit_code"):
        assert forbidden not in " ".join(cells["label"])


def test_the_building_headline_names_the_best_and_the_worst_from_the_data():
    cells = ui.building_cells(SYNTHETIC, "en")
    ordered = cells.sort_values("net_pct_shrunk", ascending=False)
    headline = ui.building_headline(cells, "en")
    assert ordered.iloc[0]["building"] in headline and ordered.iloc[-1]["building"] in headline
    assert f"{ordered.iloc[0]['net_pct_shrunk']:.1f} %" in headline
    assert ui.building_headline(None, "en") == t("bd_headline_empty", "en")
    one = cells[cells["building"] == ordered.iloc[0]["building"]]
    assert t("bd_headline_one", "en", best=ordered.iloc[0]["building"], best_pct=ui.pct(one["net_pct_shrunk"].max())) \
        .split(" is at")[0] in ui.building_headline(one, "en")


def test_building_dots_are_sorted_best_first_sized_by_pairs_and_capped():
    cells = ui.building_cells(SYNTHETIC, "en")
    markup = ui.building_dots(cells, "en")
    labels = re.findall(r'<div title="([^"]+)">', markup)
    ordered = cells.sort_values("net_pct_shrunk", ascending=False, kind="stable")
    assert [html.unescape(label) for label in labels] == list(ordered["label"])
    widths = [float(width) for width in re.findall(r"width:([0-9.]+)px", markup)]
    assert max(widths) <= ui.DOT_MAX_PX and min(widths) >= ui.DOT_BASE_PX
    huge = cells.assign(n_pairs=10_000)
    assert max(float(w) for w in re.findall(r"width:([0-9.]+)px", ui.building_dots(huge, "en"))) == ui.DOT_MAX_PX


# ---------------------------------------------------------------------------
# Validation: the ranking is the pipeline's own rule
# ---------------------------------------------------------------------------
def test_the_ranking_champion_is_the_pipelines_and_the_headline_model():
    figures = ui.validation_figures(SYNTHETIC, CFG)
    table = pd.DataFrame(SYNTHETIC["backtest"]).rename(columns={"information_rule": "rule"})
    table["abs_error_pp_net"] = table["error_pp_net"].abs()
    assert figures["champion"] == select_champion(table, CFG)["champion"] == SYNTHETIC["headline"]["model"]
    assert [model["champion"] for model in figures["models"]].count(True) == 1 and figures["models"][0]["champion"]


def test_the_bars_use_only_the_selection_years_and_the_holdout_is_apart():
    figures = ui.validation_figures(SYNTHETIC, CFG)
    for model in figures["models"]:
        assert set(model["years"]) == set(figures["selection_years"])
        assert figures["holdout_year"] not in model["years"]
        assert model["mean"] == pytest.approx(sum(model["years"].values()) / len(model["years"]))
        assert model["holdout"] is not None
    best = min(figures["models"], key=lambda model: model["mean"])
    assert best["champion"]                                                  # lowest selection error = the champion


def test_the_left_chart_is_the_headline_models_forecast_and_actual_per_year():
    figures = ui.validation_figures(SYNTHETIC, CFG)
    rows = [row for row in SYNTHETIC["backtest"] if row["model"] == SYNTHETIC["headline"]["model"]
            and row["information_rule"] == SYNTHETIC["headline"]["information_rule"]]
    assert [row["year"] for row in figures["left"]] == sorted(row["year"] for row in rows)
    first = figures["left"][0]
    assert first["forecast"] == next(row["forecast_net_pct"] for row in rows if row["year"] == first["year"])


def test_the_validation_headline_compares_model_spread_with_year_spread():
    assert ui.validation_headline({"model_spread": 0.2, "year_spread": 1.0}, "en") == t("val_headline_less", "en")
    assert ui.validation_headline({"model_spread": 2.0, "year_spread": 1.0}, "en") == t("val_headline_more", "en")
    assert ui.validation_headline({"model_spread": None, "year_spread": 1.0}, "en") == t("val_headline_na", "en")


def test_the_mae_chart_marks_the_champion_the_ticks_and_the_holdout():
    markup = ui.mae_chart(ui.validation_figures(SYNTHETIC, CFG)["models"], "en")
    assert markup.count("ll-fill lead") == 1 and markup.count("ll-hollow") == len(SYNTHETIC_MODELS)
    assert markup.count("ll-tick") == len(SYNTHETIC_MODELS) * len(CFG["forecast_years"]["selection_years"])


SYNTHETIC_MODELS = {row["model"] for row in SYNTHETIC["backtest"]}


# ---------------------------------------------------------------------------
# Labels and theme
# ---------------------------------------------------------------------------
def test_french_and_english_labels_have_identical_keys_and_placeholders():
    import string
    assert set(LABELS["fr"]) == set(LABELS["en"])
    for key in LABELS["en"]:
        fields = {language: {name for _, name, _, _ in string.Formatter().parse(LABELS[language][key]) if name}
                  for language in LANGS}
        assert fields["en"] == fields["fr"], key
        assert all(LABELS[language][key].strip() for language in LANGS), key


def test_every_label_is_used_somewhere():
    sources = "\n".join(path.read_text(encoding="utf-8") for path in (repo_root() / "app").rglob("*.py")
                        if path.name != "labels.py")
    built_from_a_prefix = ("why_step_", "why_title_", "why_body_", "opt_incentive_", "opt_renewal_", "opt_newbuild_", "province_",
                           "as_", "va_", "no_key_", "val_headline_", "topic_")                   # keys assembled with an f-string
    unused = [key for key in LABELS["en"]
              if not key.startswith(built_from_a_prefix + ("tab_",)) and f'"{key}"' not in sources and f"'{key}'" not in sources]
    assert not unused, unused


def test_the_theme_colours_in_config_toml_equal_the_design_tokens():
    config = (repo_root() / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    for name, value in (("backgroundColor", theme.PAPER), ("secondaryBackgroundColor", theme.SURFACE),
                        ("textColor", theme.INK), ("primaryColor", theme.ACCENT_TEXT)):
        assert f'{name} = "{value}"' in config, name
    assert 'font = "serif"' in config and "headless = true" in config


def test_the_css_carries_the_hand_off_tokens_and_hides_the_streamlit_chrome():
    css = theme.CSS
    for token in (theme.PAPER, theme.SURFACE, theme.INK, theme.ACCENT, theme.ACCENT_TEXT, theme.SECOND, theme.SECOND_TEXT,
                  *theme.NEUTRALS, "Source+Serif+4", "max-width:1120px", "padding:0 40px 120px", "outline:2px solid",
                  "clamp(120px", "padding-top:24px", "#MainMenu", 'button[data-baseweb="tab"]'):
        assert token in css, token
    assert "sans-serif" not in css


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("lang", LANGS)
def test_the_page_runs_without_exceptions_in_both_languages(monkeypatch, lang):
    at = new_app(monkeypatch).run()
    at.radio(key="lang").set_value(lang).run()
    assert not at.exception
    text = text_of(at)
    assert t("val_weak", lang, n=len(CFG["forecast_years"]["selection_years"])) in text
    assert t("tornado_title", lang) in text and t("foot_key_note", lang) in text


@pytest.mark.parametrize("lang", LANGS)
def test_the_seven_tabs_appear_in_order_in_both_languages(monkeypatch, lang):
    at = new_app(monkeypatch, lang=lang).run()
    assert [tab.label for tab in at.tabs] == [t(f"tab_{key}", lang) for key in TAB_KEYS]
    assert len(at.tabs) == 7
    assert list(streamlit_app.VIEWS) == ["01 · Answer", "02 · Why", "03 · Validation", "04 · Scenario Lab", "05 · Buildings",
                                          "06 · Questions", "07 · Sources"]
    page = "\n".join(element.value for element in at.markdown)
    assert 'class="ll-nav"' not in page and "position:sticky" not in theme.CSS      # no anchor navigation, nothing sticky


@pytest.mark.parametrize("lang", LANGS)
def test_the_sidebar_holds_the_controls_and_the_notes(monkeypatch, lang):
    at = new_app(monkeypatch, lang=lang).run()
    assert [radio.key for radio in at.sidebar.radio] == ["lang", "data_mode"]
    assert at.sidebar.radio(key="lang").options == ["EN", "FR"]
    assert at.sidebar.radio(key="data_mode").options == [t("mode_demo", lang), t("mode_real", lang)]
    assert [button.key for button in at.sidebar.button] == ["reload"]
    assert any(t("foot_key_note", lang) == caption.value for caption in at.sidebar.caption)
    labels = [expander.label for expander in at.sidebar.expander]
    assert labels == [t("side_how_title", lang), t("foot_trust", lang)]
    notes = " ".join(element.value for element in at.sidebar.markdown)
    for key in ("trust_privacy", "trust_ai", "trust_guard", "trust_tools", "trust_font"):
        assert t(key, lang) in notes
    assert not at.main.radio                                                       # no data or language control in the main area
    assert [group.key for group in at.main.button_group] == ["lever_incentive", "lever_renewal", "lever_newbuild", "lever_rule"]


def test_the_masthead_title_and_badge_sit_above_the_tabs(monkeypatch):
    at = new_app(monkeypatch).run()
    top = next(element.value for element in at.main.markdown if 'class="ll-title"' in element.value)
    top = html.unescape(top)                                                       # the subtitle holds an ampersand
    assert t("app_title", "en") in top and t("badge_demo", "en") in top and t("masthead_sub", "en") in top


@pytest.mark.parametrize("lang", LANGS)
def test_deep_links_open_each_tab_without_exceptions(monkeypatch, lang):
    for key in TAB_KEYS:
        at = new_app(monkeypatch, lang=lang)
        at.query_params["view"] = key
        at.run()
        assert not at.exception, key
        assert len(at.tabs) == 7


def test_the_app_opens_in_french_by_default(monkeypatch):
    monkeypatch.setattr(streamlit_app, "_client", lambda: None)
    at = AppTest.from_function(_main, default_timeout=TIMEOUT_SECONDS).run()
    assert DEFAULT_LANG == "fr" and at.radio(key="lang").value == "fr"
    assert [tab.label for tab in at.tabs] == [t(f"tab_{key}", "fr") for key in TAB_KEYS]


def test_the_hero_is_the_first_thing_in_the_first_tab(monkeypatch):
    at = new_app(monkeypatch).run()
    first_tab = at.tabs[0]
    assert 'class="ll-hero-number"' in first_tab.markdown[0].value
    for other in at.tabs[1:]:
        assert not any('class="ll-hero-number"' in element.value for element in other.markdown)


def test_the_headline_number_comes_from_the_json(monkeypatch):
    at = new_app(monkeypatch).run()
    assert f"{SYNTHETIC['headline']['net_pct']:.1f}" in hero_html(at)


def test_the_synthetic_notice_is_shown_as_one_line(monkeypatch):
    at = new_app(monkeypatch).run()
    assert sum("ll-notice" in element.value and "SYNTHETIC EXAMPLE" in element.value for element in at.markdown) == 1
    assert not any("ll-notice" in element.value and "SYNTHÉTIQUE" in element.value for element in at.markdown)


def test_the_synthetic_notice_follows_the_interface_language(monkeypatch):
    at = new_app(monkeypatch, lang="fr").run()
    assert sum("ll-notice" in element.value and "EXEMPLE SYNTHÉTIQUE" in element.value for element in at.markdown) == 1
    assert "SYNTHETIC EXAMPLE" not in ui_notice_text(at)


def test_data_mode_is_a_sidebar_radio_and_real_without_a_file_shows_the_error(monkeypatch, tmp_path):
    monkeypatch.setattr(streamlit_app, "real_path", lambda: tmp_path / "missing.json")
    at = new_app(monkeypatch).run()
    assert at.radio(key="data_mode").options == ["Demo", "Real"]
    at.radio(key="data_mode").set_value(streamlit_app.MODE_REAL).run()
    assert not at.exception and any(t("no_real", "en") == error.value for error in at.error)


def test_an_edited_file_is_read_again_and_reload_works(monkeypatch, tmp_path):
    path = tmp_path / "aggregates.json"
    path.write_text(json.dumps(SYNTHETIC), encoding="utf-8")
    monkeypatch.setattr(streamlit_app, "synthetic_path", lambda: path)
    at = new_app(monkeypatch).run()
    first = hero_html(at)
    edited = copy.deepcopy(SYNTHETIC)
    edited["headline"]["net_pct"] = 12.3456
    time.sleep(0.01)
    path.write_text(json.dumps(edited), encoding="utf-8")
    at.run()
    assert "12.3" in hero_html(at) and hero_html(at) != first
    at.button(key="reload").click().run()
    assert not at.exception and "12.3" in hero_html(at)


def test_the_cache_key_includes_modification_time_and_size():
    assert list(streamlit_app._cached_load.__wrapped__.__code__.co_varnames[:3]) == ["path", "modified_ns", "size"]


@pytest.mark.parametrize("lang", LANGS)
def test_a_document_whose_mode_does_not_match_the_selection_is_rejected(monkeypatch, tmp_path, lang):
    document = copy.deepcopy(SYNTHETIC)
    document["mode"] = "real"
    path = tmp_path / "aggregates.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(streamlit_app, "synthetic_path", lambda: path)
    at = new_app(monkeypatch).run()
    at.radio(key="lang").set_value(lang).run()
    assert not at.exception
    assert any(t("mode_mismatch", lang, found="real", expected="synthetic") == error.value for error in at.error)
    assert not any('class="ll-hero-number"' in element.value for element in at.markdown)   # nothing from the mismatched file


def test_the_sources_tab_lists_the_series_with_their_release_dates(monkeypatch):
    at = new_app(monkeypatch).run()
    sources_tab = at.tabs[TAB_KEYS.index("sources")]
    assert t("foot_sources", "en", n=len(SYNTHETIC["sources"])) in " ".join(element.value for element in sources_tab.markdown)
    table = sources_tab.dataframe[0].value
    assert list(table[t("foot_col_release", "en")]) == [row["release_date"] for row in SYNTHETIC["sources"]]
    assert len(table) == len(SYNTHETIC["sources"])


def test_the_validation_section_warns_when_the_ranking_disagrees_with_the_headline(monkeypatch, tmp_path):
    clean = new_app(monkeypatch).run()
    assert not any("picks" in warning.value for warning in clean.warning)
    document = copy.deepcopy(SYNTHETIC)
    document["headline"]["model"] = "B1_trailing_mean" if SYNTHETIC["headline"]["model"] != "B1_trailing_mean" else "B0_last_year"
    path = tmp_path / "aggregates.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(streamlit_app, "synthetic_path", lambda: path)
    assert any("picks" in warning.value for warning in new_app(monkeypatch).run().warning)


def test_the_building_empty_state_keeps_the_info_message(monkeypatch, tmp_path):
    document = copy.deepcopy(SYNTHETIC)
    document["building_beds"] = []
    path = tmp_path / "aggregates.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(streamlit_app, "synthetic_path", lambda: path)
    at = new_app(monkeypatch).run()
    assert not at.exception and any(t("bd_empty", "en") == info.value for info in at.info)


# ---------------------------------------------------------------------------
# Scenario Lab
# ---------------------------------------------------------------------------
def grid_net(incentive, renewal, newbuild, rule="jan31"):
    row = narrative.scenario_row(SYNTHETIC, incentive, renewal, newbuild, rule)
    return f"{row['headline_net_pct']:.1f} %"


def test_the_lever_options_and_labels_follow_the_design(monkeypatch):
    at = new_app(monkeypatch).run()
    assert at.segmented_control(key="lever_incentive").options == ["Shallower", "Baseline", "Deeper"]
    assert at.segmented_control(key="lever_renewal").options == ["Fewer", "Baseline", "More"]
    assert at.segmented_control(key="lever_newbuild").options == ["Exempt", "Guideline"]
    rule_labels = at.segmented_control(key="lever_rule").options
    assert rule_labels == [ui.format_date(SYNTHETIC["as_of"]["external_cutoff"], "en"),
                           t("opt_rule_strict", "en", day=ui.format_day_month(SYNTHETIC["as_of"]["external_strict_cutoff"], "en"))]


def test_the_scenario_number_comes_only_from_the_precomputed_grid(monkeypatch):
    at = new_app(monkeypatch).run()
    assert number_in(at, "ll-scn-num") == grid_net("zero", "zero", "exempt")
    at.segmented_control(key="lever_incentive").set_value("plus").run()
    at.segmented_control(key="lever_newbuild").set_value("guideline").run()
    assert not at.exception
    assert number_in(at, "ll-scn-num") == grid_net("plus", "zero", "guideline")
    assert number_in(at, "ll-base-num") == f"{narrative.baseline_row(SYNTHETIC, 'jan31')['headline_net_pct']:.1f} %"


def test_the_delta_is_the_scenario_minus_the_baseline_in_points(monkeypatch):
    at = new_app(monkeypatch).run()
    at.segmented_control(key="lever_incentive").set_value("minus").run()
    row = narrative.scenario_row(SYNTHETIC, "minus", "zero", "exempt", "jan31")
    base = narrative.baseline_row(SYNTHETIC, "jan31")
    expected = f"{row['headline_net_pct'] - base['headline_net_pct']:+.2f} pp"
    assert expected in html.unescape(next(element.value for element in at.markdown if 'class="ll-big-row"' in element.value))


def test_a_changed_lever_gets_the_magenta_word_and_reset_clears_it(monkeypatch):
    at = new_app(monkeypatch).run()
    assert changed_markers(at) == 0
    at.segmented_control(key="lever_renewal").set_value("plus").run()
    at.segmented_control(key="lever_rule").set_value("dec31_strict").run()
    assert changed_markers(at) == 2
    at.button(key="reset_lab").click().run()
    assert not at.exception and changed_markers(at) == 0
    assert [at.segmented_control(key=key).value for key in ("lever_incentive", "lever_renewal", "lever_newbuild", "lever_rule")] \
        == ["zero", "zero", "exempt", "jan31"]
    assert number_in(at, "ll-scn-num") == grid_net("zero", "zero", "exempt")


def test_deselecting_a_lever_falls_back_to_the_baseline(monkeypatch):
    at = new_app(monkeypatch).run()
    at.segmented_control(key="lever_incentive").set_value(None).run()
    assert not at.exception and number_in(at, "ll-scn-num") == grid_net("zero", "zero", "exempt")


def test_the_scenario_text_is_the_narrative_fallback_text(monkeypatch):
    at = new_app(monkeypatch).run()
    row = narrative.scenario_row(SYNTHETIC, "zero", "zero", "exempt", "jan31")
    expected = narrative.fallback_scenario_text(row, narrative.baseline_row(SYNTHETIC, "jan31"), "en")
    assert any(expected == element.value for element in at.markdown)


def test_a_missing_grid_row_is_said_plainly(monkeypatch, tmp_path):
    document = copy.deepcopy(SYNTHETIC)
    document["scenario_grid"] = [row for row in document["scenario_grid"] if row["incentive_shift"] != "plus"]
    path = tmp_path / "aggregates.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(streamlit_app, "synthetic_path", lambda: path)
    at = new_app(monkeypatch).run()
    at.segmented_control(key="lever_incentive").set_value("plus").run()
    assert not at.exception and t("lab_no_row", "en") in text_of(at)


# ---------------------------------------------------------------------------
# Ask the analysis: every status, calmly
# ---------------------------------------------------------------------------
def _ask_view(document, lang):
    from app.streamlit_app import ask_analysis_view

    ask_analysis_view(document, lang)


def ask_app(monkeypatch, ask=None, key=False, lang="en") -> AppTest:
    monkeypatch.setattr(streamlit_app, "_client", lambda: object() if key else None)
    if ask is not None:
        monkeypatch.setattr(qa_answers, "answer_question", ask)
    return AppTest.from_function(_ask_view, args=(SYNTHETIC, lang), default_timeout=TIMEOUT_SECONDS).run()


def lab_app(monkeypatch, copilot=None) -> AppTest:
    if copilot is not None:
        monkeypatch.setattr(narrative, "scenario_copilot", copilot)
    return new_app(monkeypatch, client=object()).run()


ROW = narrative.scenario_row(SYNTHETIC, "plus", "zero", "guideline", "dec31_strict")


@pytest.mark.parametrize("failure", [TimeoutError("provider timed out"), ConnectionError("network down"), RuntimeError("boom")])
def test_a_provider_failure_shows_a_short_message_and_keeps_the_levers(monkeypatch, failure):
    def failing(*args, **kwargs):
        raise failure

    at = ask_app(monkeypatch, ask=failing)
    at.button(key="pill_0").click().run()
    assert not at.exception and t("ask_fallback", "en") in text_of(at)
    assert "Traceback" not in text_of(at) and str(failure) not in text_of(at)
    broken = lab_app(monkeypatch, copilot=failing)
    broken.text_input(key="copilot_question").input("explain").run()
    broken.button(key="copilot_go").click().run()
    assert not broken.exception and t("ask_error", "en") in text_of(broken)
    assert broken.segmented_control(key="lever_rule").value == "jan31"


@pytest.mark.parametrize("lang", LANGS)
def test_the_five_preset_questions_are_buttons_answered_in_the_page_language(monkeypatch, lang):
    at = ask_app(monkeypatch, lang=lang)
    pills = [button for button in at.button if str(button.key).startswith("pill_")]
    assert [button.label for button in pills] == streamlit_app._pills(lang) and len(pills) == 5
    for index in range(5):
        at.button(key=f"pill_{index}").click().run()
        assert not at.exception and not at.info and not at.warning
        page = text_of(at)
        assert t("ask_note", lang) in page
        assert at.session_state["asked"] == streamlit_app._pills(lang)[index]
        assert "§" not in page and not re.search(r"\b[BE]\d_[a-z_]+\b", page)
        assert qa_answers.CAPTION["synthetic"][lang] in page
        assert ("Read more in the notebook" if lang == "en" else "Pour approfondir") in page


def test_a_free_question_runs_only_when_answer_is_pressed(monkeypatch):
    seen = []
    at = ask_app(monkeypatch, ask=lambda question, *a, **k: (seen.append(question), qa_answers.compose("headline", SYNTHETIC, "fr")[0])[1])
    at.text_input(key="free_question").input("Quelle est la hausse ?").run()
    assert seen == []
    at.button(key="answer_go").click().run()
    assert seen == ["Quelle est la hausse ?"]


def test_an_occupancy_question_gets_a_friendly_refusal_and_no_number(monkeypatch):
    at = ask_app(monkeypatch)
    at.text_input(key="free_question").input("What is the occupancy rate?").run()
    at.button(key="answer_go").click().run()
    page = text_of(at)
    assert not at.exception and qa_answers.REFUSAL["en"][0] in page
    assert not re.search(r"\d", qa_answers.REFUSAL["en"][0])


def test_the_copilot_link_appears_only_when_a_client_exists(monkeypatch):
    without = new_app(monkeypatch).run()
    assert "copilot_question" not in [widget.key for widget in without.text_input]
    assert not any(button.key == "copilot_go" for button in without.button)
    with_client = lab_app(monkeypatch)
    assert "copilot_question" in [widget.key for widget in with_client.text_input]


def test_the_copilot_text_is_shown_as_returned_and_the_scenario_it_chose_appears_as_chips(monkeypatch):
    answer = {"status": "ai", "text": "COPILOT TEXT", "row": ROW}
    at = lab_app(monkeypatch, copilot=lambda question, doc, client, rule="jan31": answer)
    at.text_input(key="copilot_question").input("what if incentives rise").run()
    at.button(key="copilot_go").click().run()
    assert not at.exception
    assert "COPILOT TEXT" in text_of(at) and t("lab_understood", "en") in text_of(at)
    chips = " ".join(element.value for element in at.markdown if 'class="ll-chip"' in element.value)
    for expected in (t("opt_incentive_plus", "en"), t("opt_newbuild_guideline", "en")):
        assert expected in chips


def test_the_copilots_text_is_not_rebuilt_from_the_lever_rule(monkeypatch):
    answer = {"status": "fallback", "text": "TEXT BUILT BY THE COPILOT", "row": ROW}
    at = lab_app(monkeypatch, copilot=lambda question, doc, client, rule="jan31": answer)
    at.text_input(key="copilot_question").input("scenario").run()
    at.button(key="copilot_go").click().run()
    assert "TEXT BUILT BY THE COPILOT" in text_of(at)
    rebuilt = narrative.fallback_scenario_text(ROW, narrative.baseline_row(SYNTHETIC, "jan31"), "en")
    assert not any(rebuilt == element.value for element in at.markdown)


def test_the_lever_selection_is_passed_to_the_copilot_when_it_accepts_one(monkeypatch):
    seen = {}

    def copilot(question, doc, client, rule="jan31", selection=None):
        seen.update(rule=rule, selection=selection)
        return {"status": "ai", "text": "ok", "row": ROW}

    at = lab_app(monkeypatch, copilot=copilot)
    at.segmented_control(key="lever_incentive").set_value("plus").run()
    at.segmented_control(key="lever_newbuild").set_value("guideline").run()
    at.text_input(key="copilot_question").input("q").run()
    at.button(key="copilot_go").click().run()
    assert seen["selection"] == {"incentive": "plus", "renewal": "zero", "newbuild": "guideline", "rule": "jan31"}


def test_the_copilot_still_works_without_a_selection_parameter(monkeypatch):
    seen = {}

    def copilot(question, doc, client, rule="jan31"):
        seen["rule"] = rule
        return {"status": "ai", "text": "ok", "row": ROW}

    at = lab_app(monkeypatch, copilot=copilot)
    at.text_input(key="copilot_question").input("q").run()
    at.button(key="copilot_go").click().run()
    assert not at.exception and seen["rule"] == "jan31"


# ---------------------------------------------------------------------------
# Fix round 1: colours, null safety, font note, building phases
# ---------------------------------------------------------------------------
def test_net_and_contractual_tokens_are_the_contracts_colours():
    assert theme.NET == COLOR_NET and theme.CONTRACT == COLOR_CONTRACT
    assert f"--net:{COLOR_NET}" in theme.CSS and f"--contract:{COLOR_CONTRACT}" in theme.CSS


def test_everything_that_means_net_or_contractual_uses_those_colours():
    css = re.sub(r"\s+", " ", theme.CSS)
    for selector in (".ll-hero-number", ".ll-marker.net", ".ll-marker.contract", ".ll-fill.lead", ".ll-fill.actual",
                     ".ll-fill.forecast", ".ll-bd-dot", ".ll-scn-num", ".ll-base-num", ".ll-dot.scenario", ".ll-legend i.net",
                     ".ll-legend i.contract"):
        rule = css[css.index(selector + " {"):].split("}")[0]
        assert "var(--net)" in rule or "var(--contract)" in rule, selector
    assert "var(--accent" not in css[css.index(".ll-hero-number {"):].split("}")[0]


def test_the_hero_and_the_legend_use_the_net_and_contractual_classes():
    markup = ui.hero(SYNTHETIC, "en")
    assert 'class="ll-marker net"' in markup and 'class="ll-marker contract"' in markup
    assert '<i class="net">' in markup and '<i class="contract">' in markup


def null_document() -> dict:
    """A document with null in every field the schema allows to be null (the schema is the contract)."""
    document = copy.deepcopy(SYNTHETIC)
    head = document["headline"]
    head.update(net_pct=None, contract_pct=None, model=None)
    head["model_range"] = {"low_net_pct": None, "high_net_pct": None}
    head["provinces"] = {code: {"net_pct": None, "contract_pct": None} for code in ("QC", "ON")}
    document["companions"] = {"median_net_pct": None, "median_contract_pct": None}
    document["scenarios"] = {"low_net_pct": None, "central_net_pct": None, "high_net_pct": None}
    for row in document["backtest"][::2]:
        row.update(forecast_net_pct=None, actual_net_pct=None, error_pp_net=None, forecast_contract_pct=None,
                   actual_contract_pct=None, error_pp_contract=None)
    for row in document["scenario_grid"]:
        row.update(headline_net_pct=None, headline_contract_pct=None)
    for row in document["building_beds"]:
        row.update(net_pct_raw=None, net_pct_shrunk=None, contract_pct_raw=None, contract_pct_shrunk=None)
    for row in document["sensitivity"]:
        row.update(headline_net_pct=None, base_net_pct=None, delta_pp=None)
    return document


def serve(monkeypatch, tmp_path, document, lang="en") -> AppTest:
    path = tmp_path / "aggregates.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(streamlit_app, "synthetic_path", lambda: path)
    return new_app(monkeypatch, lang=lang)


def test_the_null_document_is_valid_against_the_schema(tmp_path):
    path = tmp_path / "aggregates.json"
    path.write_text(json.dumps(null_document()), encoding="utf-8")
    assert streamlit_app.load_aggregates(path)["headline"]["net_pct"] is None


@pytest.mark.parametrize("lang", LANGS)
def test_every_tab_renders_a_document_full_of_nulls_without_exceptions(monkeypatch, tmp_path, lang):
    at = serve(monkeypatch, tmp_path, null_document(), lang).run()
    assert not at.exception and len(at.tabs) == 7
    assert "nan" not in text_of(at).lower().replace("financ", "")                # no raw float ever leaks
    hero = next(element.value for element in at.markdown if 'class="ll-hero-number"' in element.value)
    assert ui.MISSING in hero and 'class="ll-marker net"' not in hero
    assert t("lab_no_row", lang) in text_of(at)


def test_the_lab_never_words_or_subtracts_null_figures(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("fallback_scenario_text must not be called with null values")

    monkeypatch.setattr(narrative, "fallback_scenario_text", forbidden)
    at = serve(monkeypatch, tmp_path, null_document()).run()
    for incentive in ("minus", "plus"):
        at.segmented_control(key="lever_incentive").set_value(incentive).run()
        assert not at.exception, incentive
    assert number_in(at, "ll-scn-num") is None and number_in(at, "ll-delta") is None


def test_a_single_null_grid_row_gives_the_no_row_message_and_the_rest_still_works(monkeypatch, tmp_path):
    document = copy.deepcopy(SYNTHETIC)
    for row in document["scenario_grid"]:
        if (row["incentive_shift"], row["renewal_shift"], row["newbuild_regime"], row["information_rule"]) == ("plus", "zero", "exempt", "jan31"):
            row.update(headline_net_pct=None, headline_contract_pct=None)
    at = serve(monkeypatch, tmp_path, document).run()
    assert number_in(at, "ll-scn-num") == grid_net("zero", "zero", "exempt")
    at.segmented_control(key="lever_incentive").set_value("plus").run()
    assert not at.exception and t("lab_no_row", "en") in text_of(at) and number_in(at, "ll-scn-num") is None
    at.segmented_control(key="lever_incentive").set_value("minus").run()
    assert number_in(at, "ll-scn-num") == grid_net("minus", "zero", "exempt")


def test_null_building_values_are_left_out_of_the_headline_and_the_dots():
    document = copy.deepcopy(SYNTHETIC)
    document["building_beds"][0].update(net_pct_shrunk=None, net_pct_raw=None)
    cells = ui.building_cells(document, "en")
    assert len(cells) == len(SYNTHETIC["building_beds"])                             # the table keeps every cell
    assert cells.iloc[0]["label"] not in ui.building_dots(cells, "en")
    assert "nan" not in ui.building_headline(cells, "en").lower()
    assert ui.building_dots(cells.assign(net_pct_shrunk=None), "en") == ""
    assert ui.building_headline(cells.assign(net_pct_shrunk=None), "en") == t("bd_headline_empty", "en")


def test_the_headline_model_may_be_null():
    document = null_document()
    assert ui.model_name(document) == ui.MISSING
    assert ui.MISSING in ui.hero(document, "en") and ui.validation_figures(document, CFG)["left"] == []


def test_a_missing_value_formats_as_n_a_never_as_nan():
    assert ui.pct(None) == ui.pct(float("nan")) == "n/a" and ui.pp(None) == ui.pp(float("nan")) == "n/a"


def test_the_font_note_is_in_the_trust_notes_and_the_font_comment_is_explicit():
    assert "Google Fonts" in t("trust_font", "en") and "no data sent" in t("trust_font", "en")
    assert ("Police chargée depuis Google Fonts (aucune donnée envoyée) ; hors ligne, une police système est utilisée."
            in t("trust_font", "fr"))
    source = (repo_root() / "app" / "ui" / "theme.py").read_text(encoding="utf-8")
    assert "none of the app's data" in source and "Georgia" in source and "Source Serif 4" in theme.FONT_FAMILY


def cell(building, beds, pairs):
    return {"building": building, "beds": beds, "n_pairs": pairs, "net_pct_raw": 3.0 + pairs / 100,
            "net_pct_shrunk": 3.0 + pairs / 100, "contract_pct_raw": 4.0, "contract_pct_shrunk": 4.0}


# the same two property cells of one building (A has 1 and 2 bedrooms, B has 1 and 2), in the two ways an export may sort them
CELL_FIRST = [cell("Building A", 1, 12), cell("Building A", 2, 8), cell("Building A", 1, 21), cell("Building A", 2, 9)]
BEDS_FIRST = [cell("Building A", 1, 12), cell("Building A", 1, 21), cell("Building A", 2, 8), cell("Building A", 2, 9)]


@pytest.mark.parametrize("order", [CELL_FIRST, BEDS_FIRST], ids=["cell-first", "beds-first"])
@pytest.mark.parametrize("lang", LANGS)
def test_building_labels_stay_unique_in_either_export_order(order, lang):
    document = copy.deepcopy(SYNTHETIC)
    document["building_beds"] = copy.deepcopy(order)
    cells = ui.building_cells(document, lang)
    assert cells["label"].is_unique and len(cells) == 4
    assert sorted(cells["phase"]) == [1, 1, 2, 2]                                    # each bedroom count has a phase 1 and a phase 2
    assert all("phase" in label.lower() or t("bd_phase", lang, phase=1).split()[0] in label for label in cells["label"])
    dots = ui.building_dots(cells, lang)
    assert {html.unescape(label) for label in re.findall(r'<div title="([^"]+)">', dots)} == set(cells["label"])


@pytest.mark.parametrize("order", [CELL_FIRST, BEDS_FIRST], ids=["cell-first", "beds-first"])
def test_the_table_and_the_dots_show_the_same_cells_in_either_export_order(monkeypatch, tmp_path, order):
    document = copy.deepcopy(SYNTHETIC)
    document["building_beds"] = copy.deepcopy(order)
    at = serve(monkeypatch, tmp_path, document).run()
    assert not at.exception
    tab = at.tabs[TAB_KEYS.index("buildings")]
    table_labels = set(tab.dataframe[0].value[t("bd_col_cell", "en")])
    dot_labels = {html.unescape(label) for element in tab.markdown for label in re.findall(r'<div title="([^"]+)">', element.value)}
    assert table_labels == dot_labels == set(ui.building_cells(document, "en")["label"])


def test_a_building_with_an_extra_cell_never_gets_a_guessed_phase():
    """Cell B only has 3 bedrooms: that row is unique for its building and bedroom count, so it carries no phase word."""
    document = copy.deepcopy(SYNTHETIC)
    document["building_beds"] = [cell("Building A", 1, 12), cell("Building A", 2, 8), cell("Building A", 3, 5)]
    labels = list(ui.building_cells(document, "en")["label"])
    assert all("phase" not in label for label in labels) and len(set(labels)) == 3


# ---------------------------------------------------------------------------
# Privacy and packaging
# ---------------------------------------------------------------------------
APP_FILES = ["streamlit_app.py", "ui/labels.py", "ui/theme.py", "ui/components.py", "ui/__init__.py"]


@pytest.mark.parametrize("name", APP_FILES)
def test_the_app_files_name_no_crm_path_and_no_network_library(name):
    source = (repo_root() / "app" / name).read_text(encoding="utf-8")
    assert "data/private" not in source
    for forbidden in ("requests", "httpx", "urllib", "import anthropic", "read_csv", ".csv", "matplotlib"):
        assert forbidden not in source, (name, forbidden)


def test_the_only_external_address_is_the_font_stylesheet():
    addresses = set()
    for name in APP_FILES:
        addresses |= set(re.findall(r"https?://[^\s'\")]+", (repo_root() / "app" / name).read_text(encoding="utf-8")))
    assert {address.split("/")[2] for address in addresses} == {"fonts.googleapis.com"}


def test_a_demo_session_reads_no_csv_and_no_crm_path(monkeypatch):
    read = []
    original = pathlib.Path.read_text
    monkeypatch.setattr(pathlib.Path, "read_text", lambda self, *args, **kwargs: (read.append(str(self)),
                                                                                  original(self, *args, **kwargs))[1])
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: pytest.fail("the app must not read CSV files"))
    at = new_app(monkeypatch).run()
    at.radio(key="lang").set_value("fr").run()
    assert not at.exception
    assert read and not any("data/private" in path or path.endswith(".csv") for path in read)
    assert all("outputs/private" not in path for path in read)


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


def test_the_old_module_name_still_resolves_to_the_package():
    from app.ui import t as label

    assert label("app_title", "en") == "Halo Lens" and DEFAULT_LANG in LANGS


def test_no_app_constant_is_defined_and_never_used():
    import ast
    texts = {path.relative_to(repo_root() / "app").as_posix(): path.read_text(encoding="utf-8")
             for path in (repo_root() / "app").rglob("*.py")}
    everything = "\n".join(texts.values()) + "\n".join(
        path.read_text(encoding="utf-8") for path in (repo_root() / "tests").glob("test_app*.py"))
    for name in ("ui/theme.py", "ui/components.py", "streamlit_app.py"):
        tree = ast.parse(texts[name])
        constants = [node.targets[0].id for node in tree.body if isinstance(node, ast.Assign)
                     and isinstance(node.targets[0], ast.Name) and node.targets[0].id.isupper()]
        for constant in constants:
            assert len(re.findall(rf"\b{constant}\b", everything)) >= 2, f"{name}: {constant} is never used"
