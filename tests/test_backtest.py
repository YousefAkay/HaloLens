"""Tests for error metrics and the backtest skeleton (evaluate.metrics, evaluate.backtest). Owner: FCT.

Uses the same hand-made leases as test_baselines (known yearly growth). `run_backtest` uses
`forecast.combine.forecast` (F-05).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from halolens.evaluate.backtest import (actual_for_year, backtest_all_models, backtest_baselines, backtest_both_rules,
                                         run_backtest, select_champion, summarize_models)
from halolens.evaluate.metrics import absolute_error_pp, mean_absolute_error_pp, signed_error_pp
from halolens.forecast.asof import make_snapshot
from halolens.forecast.baselines import BASELINES, frozen_weights, training_pairs
from halolens.config import cutoff_for
from tests.test_baselines import (ABS_TOLERANCE_PP, YEARLY_GROWTH, annual_leases, empty_external, market_rows,
                                  tables_from)

PERCENT_OF_GROWTH = 100


@pytest.fixture(scope="module")
def tables():
    return tables_from(annual_leases())


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def test_signed_error_is_forecast_minus_actual():
    assert signed_error_pp(3.0, 5.0) == pytest.approx(-2.0)
    assert signed_error_pp(5.0, 3.0) == pytest.approx(2.0)


def test_absolute_error_ignores_the_sign():
    assert absolute_error_pp(3.0, 5.0) == pytest.approx(2.0)
    assert absolute_error_pp(5.0, 3.0) == pytest.approx(2.0)


def test_mean_absolute_error_skips_nan_and_handles_empty():
    assert mean_absolute_error_pp([-1.0, 3.0, np.nan]) == pytest.approx(2.0)
    assert np.isnan(mean_absolute_error_pp([np.nan]))


# ---------------------------------------------------------------------------
# actual_for_year
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("year", [2023, 2024, 2025])
def test_actual_for_year_matches_the_known_growth(year, tables, cfg):
    cutoff = cutoff_for(year, cfg)
    weights = frozen_weights(training_pairs(make_snapshot(tables, empty_external(), cutoff), cfg), cutoff, cfg)
    actual = actual_for_year(tables, year, weights, cfg)
    assert actual["net_pct"] == pytest.approx(YEARLY_GROWTH[year] * PERCENT_OF_GROWTH, abs=ABS_TOLERANCE_PP)
    assert actual["median_net_pct"] == pytest.approx(actual["net_pct"], abs=ABS_TOLERANCE_PP)
    assert actual["weight_coverage"] == pytest.approx(1.0)
    assert actual["n_pairs"] > 0


def test_actual_is_winsorized_at_bounds_learned_before_the_cutoff(cfg):
    """A 20% year is clipped to the highest growth known at the cutoff (5%): thresholds never come from the year itself."""
    extreme = tables_from(annual_leases({**YEARLY_GROWTH, 2025: 0.20}))
    cutoff = cutoff_for(2025, cfg)
    weights = frozen_weights(training_pairs(make_snapshot(extreme, empty_external(), cutoff), cfg), cutoff, cfg)
    actual = actual_for_year(extreme, 2025, weights, cfg)
    assert actual["net_pct"] == pytest.approx(max(YEARLY_GROWTH.values()) * PERCENT_OF_GROWTH, abs=ABS_TOLERANCE_PP)


def test_actual_for_year_without_pairs_raises(tables, cfg):
    cutoff = cutoff_for(2025, cfg)
    weights = frozen_weights(training_pairs(make_snapshot(tables, empty_external(), cutoff), cfg), cutoff, cfg)
    with pytest.raises(ValueError, match="No eligible pairs"):
        actual_for_year(tables, 2031, weights, cfg)


# ---------------------------------------------------------------------------
# Baseline backtest table
# ---------------------------------------------------------------------------
def test_baseline_backtest_has_one_row_per_model_and_year(tables, cfg):
    result = backtest_baselines(tables, market_rows(), cfg)
    years = cfg["forecast_years"]["backtest_years"]
    assert len(result) == len(BASELINES) * len(years)
    assert set(result["model"]) == set(BASELINES)
    assert set(result["year"]) == set(years)


def test_b0_errors_equal_last_years_growth_minus_this_years(tables, cfg):
    """Growth rises 1 pp a year in 2023-2025, so the last-year baseline is 1 pp low every time."""
    result = backtest_baselines(tables, market_rows(), cfg)
    b0 = result[result["model"] == "B0_last_year"]
    assert b0["error_pp_net"].tolist() == pytest.approx([-1.0] * len(b0), abs=ABS_TOLERANCE_PP)
    assert b0["abs_error_pp_net"].tolist() == pytest.approx([1.0] * len(b0), abs=ABS_TOLERANCE_PP)


def test_error_is_forecast_minus_actual_in_the_table(tables, cfg):
    result = backtest_baselines(tables, market_rows(), cfg)
    computed = result["forecast_net_pct"] - result["actual_net_pct"]
    pd.testing.assert_series_equal(computed, result["error_pp_net"], check_names=False)


def test_missing_market_data_keeps_the_b2_rows_visible_with_a_note(tables, cfg):
    result = backtest_baselines(tables, empty_external(), cfg)
    b2 = result[result["model"] == "B2_market_anchor"]
    assert len(b2) == len(cfg["forecast_years"]["backtest_years"])
    assert b2["forecast_net_pct"].isna().all()
    assert b2["note"].str.contains("market").all()
    assert result[result["model"] == "B0_last_year"]["forecast_net_pct"].notna().all()


def test_backtest_folds_do_not_see_future_leases(tables, cfg):
    """The 2023 fold must not change when every lease from 2024 onward is removed from the source table."""
    leases = tables.leases
    early_only = tables_from(leases[leases["lease_start"] < pd.Timestamp("2024-01-01")])
    full = backtest_baselines(tables, market_rows(), cfg, years=[2023])
    early = backtest_baselines(early_only, market_rows(), cfg, years=[2023])
    pd.testing.assert_series_equal(full["forecast_net_pct"], early["forecast_net_pct"])


def test_baseline_backtest_runs_on_the_synthetic_fixtures(raw, cfg):
    """Done-when check: baselines backtest on synthetic data (aggregates only)."""
    from halolens.io import canonicalize
    result = backtest_baselines(canonicalize(raw), empty_external(), cfg)
    assert result[result["model"] != "B2_market_anchor"]["error_pp_net"].notna().any()


def test_run_backtest_uses_the_same_forecast_as_the_engine_pipeline(raw, cfg):
    """backtest() must call the very forecast() behind estimate_2026(): same snapshot, same numbers."""
    from halolens.forecast.combine import forecast
    from halolens.io import canonicalize
    synthetic = canonicalize(raw)
    fold = run_backtest(synthetic, empty_external(), 2025, cfg)
    direct = forecast(make_snapshot(synthetic, empty_external(), cutoff_for(2025, cfg)), cfg)
    assert fold.forecast.headline_net_pct == direct.headline_net_pct
    assert fold.error_pp_net == pytest.approx(direct.headline_net_pct - fold.actual_net_pct)
    assert fold.target_year == 2025 and fold.coverage["n_pairs_actual"] > 0


def test_all_models_table_adds_the_engine_to_the_baselines(raw, cfg):
    from halolens.io import canonicalize
    table = backtest_all_models(canonicalize(raw), empty_external(), cfg)
    assert set(table["model"]) == set(BASELINES) | {"E1_engine_blend", "E2_regulated"}
    engine = table[table["model"] == "E1_engine_blend"]
    assert engine["forecast_net_pct"].notna().all() and engine["note"].eq("").all()
    regulated = table[table["model"] == "E2_regulated"]          # no TAL rows in this fixture: visible NaN rows with a reason
    assert regulated["forecast_net_pct"].isna().all() and regulated["note"].str.contains("rate").all()


def test_model_summary_separates_selection_years_from_the_holdout(raw, cfg):
    from halolens.io import canonicalize
    table = backtest_all_models(canonicalize(raw), empty_external(), cfg)
    summary = summarize_models(table, cfg).set_index("model")
    engine = table[table["model"] == "E1_engine_blend"].set_index("year")["abs_error_pp_net"]
    selection = cfg["forecast_years"]["selection_years"]
    assert summary.loc["E1_engine_blend", "mae_selection_pp"] == pytest.approx(engine.loc[selection].mean())
    assert summary.loc["E1_engine_blend", "mae_holdout_pp"] == pytest.approx(engine.loc[cfg["forecast_years"]["holdout_year"]])
    assert summary.loc["E1_engine_blend", "n_folds_run"] == len(engine)
    assert summary.loc["B2_market_anchor", "n_folds_run"] == 0   # no external data in this fixture


# ---------------------------------------------------------------------------
# Information-date rules (REQUEST-INT-01): Jan-31 rule vs Dec-31 strict sensitivity
# ---------------------------------------------------------------------------
def january_release_market(year: int) -> pd.DataFrame:
    """Market rows for ref years year-3 .. year-1 where the latest (year-1) is released on January 15 of `year`."""
    frame = market_rows(include_post_cutoff=False)
    latest = frame["ref_period_end"].dt.year == year - 1
    frame.loc[latest, "release_date"] = pd.Timestamp(f"{year}-01-15")
    return frame


def test_b2_uses_a_january_release_under_the_jan_31_rule_but_not_under_the_strict_rule(tables, cfg):
    from halolens.forecast.baselines import market_anchor
    from halolens.forecast.asof import snapshot_for_year
    external = january_release_market(2025)
    jan31 = market_anchor(snapshot_for_year(tables, external, 2025, cfg), cfg)
    strict = market_anchor(snapshot_for_year(tables, external, 2025, cfg, strict=True), cfg)
    assert jan31.components["market_year"] == 2024        # released Jan 15, inside the agreed window
    assert strict.components["market_year"] == 2023       # strict rule: the 2024 value is not yet public
    assert jan31.headline_net_pct != strict.headline_net_pct


def test_models_that_never_read_external_data_are_identical_under_both_rules(tables, cfg):
    external = january_release_market(2025)
    jan31 = backtest_all_models(tables, external, cfg, years=[2025]).set_index("model")
    strict = backtest_all_models(tables, external, cfg, years=[2025], strict=True).set_index("model")
    assert jan31.loc["B2_market_anchor", "rule"] == "jan31" and strict.loc["B2_market_anchor", "rule"] == "dec31_strict"
    for name in ("B0_last_year", "B1_trailing_mean", "E1_engine_blend"):   # E1 is NaN here (too few leases): equal either way
        pd.testing.assert_series_equal(jan31.loc[[name], "forecast_net_pct"], strict.loc[[name], "forecast_net_pct"])


def test_both_rules_table_has_one_block_per_rule(tables, cfg):
    table = backtest_both_rules(tables, january_release_market(2025), cfg, years=[2025])
    assert set(table["rule"]) == {"jan31", "dec31_strict"}
    assert len(table) == 2 * 6                                        # B0-B3, E1, E2 per rule
    summary = summarize_models(table, cfg)
    assert set(summary["rule"]) == {"jan31", "dec31_strict"} and len(summary) == 12


def test_table_carries_contract_and_net_forecast_and_actual(raw, cfg):
    from halolens.io import canonicalize
    table = backtest_all_models(canonicalize(raw), empty_external(), cfg, years=[2025])
    engine = table[table["model"] == "E1_engine_blend"].iloc[0]
    for column in ("forecast_net_pct", "actual_net_pct", "forecast_contract_pct", "actual_contract_pct",
                   "error_pp_net", "error_pp_contract"):
        assert np.isfinite(engine[column])
    assert engine["error_pp_contract"] == pytest.approx(engine["forecast_contract_pct"] - engine["actual_contract_pct"])


def test_run_backtest_reports_the_strict_dec_31_sensitivity(raw, cfg):
    from halolens.io import canonicalize
    fold = run_backtest(canonicalize(raw), empty_external(), 2025, cfg)
    sensitivity = fold.coverage["sensitivity_strict_dec31"]
    assert set(sensitivity) == {"forecast_net_pct", "forecast_contract_pct", "error_pp_net", "error_pp_contract"}
    assert sensitivity["forecast_net_pct"] == pytest.approx(fold.forecast.headline_net_pct)   # no external data: same


def test_run_backtest_omits_the_sensitivity_when_the_config_switches_it_off(raw, cfg):
    from halolens.io import canonicalize
    off = {**cfg, "forecast_years": {**cfg["forecast_years"], "external_cutoff_strict_sensitivity": False}}
    assert "sensitivity_strict_dec31" not in run_backtest(canonicalize(raw), empty_external(), 2025, off).coverage


# ---------------------------------------------------------------------------
# Champion selection (pre-declared: lowest mean absolute net error on the selection years, holdout never used)
# ---------------------------------------------------------------------------
def error_table(rows: list[tuple[str, int, float, str]]) -> pd.DataFrame:
    """Rows of (model, year, absolute net error, rule); the other columns are not needed for selection."""
    return pd.DataFrame(rows, columns=["model", "year", "abs_error_pp_net", "rule"])


def test_champion_has_the_lowest_selection_error_and_ignores_the_holdout(cfg):
    table = error_table([("X", 2023, 1.0, "jan31"), ("X", 2024, 1.0, "jan31"), ("X", 2025, 9.0, "jan31"),
                         ("Y", 2023, 2.0, "jan31"), ("Y", 2024, 2.0, "jan31"), ("Y", 2025, 0.0, "jan31")])
    chosen = select_champion(table, cfg)
    assert chosen["champion"] == "X"                         # Y wins on 2025, but 2025 is the holdout
    assert chosen["selection_years"] == [2023, 2024] and chosen["holdout_year"] == 2025
    ranking = chosen["ranking"].set_index("model")
    assert ranking.loc["X", "mae_selection_pp"] == pytest.approx(1.0)
    assert ranking.loc["X", "mae_holdout_pp"] == pytest.approx(9.0)      # reported, not used


def test_champion_uses_only_the_agreed_jan_31_rule(cfg):
    table = error_table([("X", 2023, 5.0, "jan31"), ("X", 2024, 5.0, "jan31"),
                         ("Y", 2023, 6.0, "jan31"), ("Y", 2024, 6.0, "jan31"),
                         ("Y", 2023, 0.1, "dec31_strict"), ("Y", 2024, 0.1, "dec31_strict")])
    assert select_champion(table, cfg)["champion"] == "X"


def test_model_missing_a_selection_year_is_not_eligible(cfg):
    table = error_table([("X", 2023, 1.0, "jan31"), ("X", 2024, np.nan, "jan31"),
                         ("Y", 2023, 3.0, "jan31"), ("Y", 2024, 3.0, "jan31")])
    chosen = select_champion(table, cfg)
    assert chosen["champion"] == "Y"
    ranking = chosen["ranking"].set_index("model")
    assert bool(ranking.loc["X", "eligible"]) is False and ranking.loc["X", "n_selection_folds_run"] == 1


def test_champion_ties_keep_table_order(cfg):
    table = error_table([("simple", 2023, 2.0, "jan31"), ("simple", 2024, 2.0, "jan31"),
                         ("complex", 2023, 2.0, "jan31"), ("complex", 2024, 2.0, "jan31")])
    assert select_champion(table, cfg)["champion"] == "simple"


def test_no_eligible_model_raises(cfg):
    table = error_table([("X", 2023, 1.0, "jan31"), ("X", 2024, np.nan, "jan31")])
    with pytest.raises(ValueError, match="selection year"):
        select_champion(table, cfg)


def test_unsupported_selection_metric_raises(cfg):
    other = {**cfg, "selection": {"metric": "rmse"}}
    with pytest.raises(ValueError, match="metric"):
        select_champion(error_table([("X", 2023, 1.0, "jan31")]), other)


def test_champion_selection_runs_on_the_full_synthetic_table(raw, cfg):
    from halolens.io import canonicalize
    table = backtest_both_rules(canonicalize(raw), empty_external(), cfg)
    chosen = select_champion(table, cfg)
    assert chosen["champion"] in set(table["model"])
    assert chosen["ranking"]["eligible"].iloc[0]


# ---------------------------------------------------------------------------
# Champion pipeline: one path behind estimate_2026() and backtest()
# ---------------------------------------------------------------------------
def test_empty_external_has_the_contract_columns_and_no_rows():
    from halolens.contracts import EXTERNAL_COLUMNS
    from halolens.evaluate.backtest import empty_external as library_empty_external
    frame = library_empty_external()
    assert list(frame.columns) == EXTERNAL_COLUMNS and frame.empty
    assert str(frame["release_date"].dtype).startswith("datetime64")


def test_tables_from_leases_leaves_concessions_and_listings_empty(raw, cfg):
    from halolens.evaluate.backtest import tables_from_leases
    from halolens.io import canonicalize
    source = canonicalize(raw)
    rebuilt = tables_from_leases(source.leases, source.asking)
    assert rebuilt.concessions.empty and rebuilt.units.empty
    assert rebuilt.leases is source.leases and rebuilt.asking is source.asking


def test_champion_pipeline_applies_the_pre_declared_rule(raw, cfg):
    from halolens.evaluate.backtest import champion_pipeline
    from halolens.io import canonicalize
    synthetic = canonicalize(raw)
    pipeline = champion_pipeline(synthetic, empty_external(), cfg)
    direct = select_champion(backtest_all_models(synthetic, empty_external(), cfg), cfg)
    assert pipeline["champion"] == direct["champion"] and callable(pipeline["forecaster"])
    assert pipeline["selection_years"] == [2023, 2024] and pipeline["holdout_year"] == 2025


def test_champion_pipeline_reuses_a_precomputed_table(raw, cfg):
    from halolens.evaluate.backtest import champion_pipeline
    from halolens.io import canonicalize
    synthetic = canonicalize(raw)
    table = backtest_all_models(synthetic, empty_external(), cfg)
    assert champion_pipeline(synthetic, empty_external(), cfg, table)["champion"] == champion_pipeline(
        synthetic, empty_external(), cfg)["champion"]


def test_champion_forecast_is_the_champions_own_forecast_for_the_target_year(raw, cfg):
    from halolens.evaluate.backtest import champion_forecast, champion_pipeline
    from halolens.forecast.asof import snapshot_for_year
    from halolens.io import canonicalize
    synthetic = canonicalize(raw)
    pipeline = champion_pipeline(synthetic, empty_external(), cfg)
    result = champion_forecast(synthetic, empty_external(), cfg)
    direct = pipeline["forecaster"](snapshot_for_year(synthetic, empty_external(), cfg["forecast_years"]["target_year"], cfg), cfg)
    assert result.model_name == direct.model_name and result.target_year == 2026
    assert result.headline_net_pct == direct.headline_net_pct


def test_champion_backtest_uses_the_same_champion_and_reports_the_sensitivity(raw, cfg):
    from halolens.evaluate.backtest import champion_backtest, champion_pipeline
    from halolens.io import canonicalize
    synthetic = canonicalize(raw)
    fold = champion_backtest(synthetic, empty_external(), 2025, cfg)
    assert fold.coverage["champion"] == champion_pipeline(synthetic, empty_external(), cfg)["champion"]
    assert fold.forecast.model_name == fold.coverage["champion"]
    assert fold.error_pp_net == pytest.approx(fold.forecast.headline_net_pct - fold.actual_net_pct)
    assert "sensitivity_strict_dec31" in fold.coverage and fold.target_year == 2025


def test_estimate_and_backtest_wrappers_share_one_champion(raw, cfg):
    """The 2026 headline and the backtest folds must come from the same model."""
    from halolens.evaluate.backtest import champion_backtest, champion_forecast, tables_from_leases
    from halolens.io import canonicalize
    source = canonicalize(raw)
    tables = tables_from_leases(source.leases, source.asking)
    estimate = champion_forecast(tables, None, cfg)
    folds = [champion_backtest(tables, None, year, cfg) for year in cfg["forecast_years"]["backtest_years"]]
    assert {fold.forecast.model_name for fold in folds} == {estimate.model_name}


def test_headline_table_lists_every_model_under_both_rules(raw, cfg):
    from halolens.evaluate.backtest import headline_table
    from halolens.io import canonicalize
    table = headline_table(canonicalize(raw), None, cfg)
    assert len(table) == 2 * 6 and set(table["rule"]) == {"jan31", "dec31_strict"}
    ran = table[table["note"] == ""]
    assert {"B0_last_year", "B1_trailing_mean", "E1_engine_blend"} <= set(ran["model"])
    assert ran[["net_pct", "contract_pct"]].notna().all().all()
    missing = table[table["model"].isin(["B2_market_anchor", "B3_tal_anchor", "E2_regulated"])]
    assert missing["net_pct"].isna().all() and missing["note"].ne("").all()   # no public data passed in


def test_headline_table_matches_the_champion_forecast_for_the_champion(raw, cfg):
    from halolens.evaluate.backtest import champion_forecast, headline_table
    from halolens.io import canonicalize
    synthetic = canonicalize(raw)
    champion = champion_forecast(synthetic, None, cfg)
    row = headline_table(synthetic, None, cfg).query("rule == 'jan31' and model == @champion.model_name").iloc[0]
    assert row["net_pct"] == pytest.approx(champion.headline_net_pct)


def test_french_date_helpers_write_dates_from_values_not_literals(cfg):
    from halolens.config import cutoff_for, external_cutoff_for
    from halolens.evaluate.backtest import french_date, french_day_month
    assert french_day_month(external_cutoff_for(2026, cfg)) == "31 janvier"
    assert french_day_month(cutoff_for(2026, cfg)) == "31 décembre"
    assert french_date(cfg["regulation"]["ontario_post_2018_exemption_cutoff"]) == "15 novembre 2018"
    assert french_date(cfg["anchors"]["tal_method_announced"]) == "17 décembre 2025"
    assert french_date("2024-08-01") == "1 août 2024" and french_date("2024-02-29").startswith("29 février")


def test_sections_08_09_10_11a_11b_type_no_dates_years_or_figures_in_markdown():
    """Numbers, dates and years in the notebook text must come from code (f-strings), not from typed Markdown."""
    import re

    import jupytext
    from halolens.config import repo_root
    allowed = re.compile(r"`[^`]*`|\\bB[0-3]\\b|\\bE[12]\\b|F-05b|estimate_2026|\\|[-| ]+\\||section \\d+")
    for name in ("08_forecast_method", "09_backtest", "10_forecast_2026", "11a_uncertainty", "11b_scenarios"):
        notebook = jupytext.read(repo_root() / "notebook" / "sections" / f"{name}.py")
        for cell in notebook.cells:
            if cell.cell_type != "markdown":
                continue
            for line in cell.source.splitlines():
                text = allowed.sub("", re.sub(r"^#+\\s*\\d+[ab]?(\\.\\d+)*\\.?\\s*", "", line) if line.startswith("#") else line)
                assert not re.search(r"\\d", text), f"{name}: typed figure in Markdown: {line.strip()[:80]}"
                assert not re.search(r"\\b(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\\b",
                                     text, re.I), f"{name}: typed month in Markdown: {line.strip()[:80]}"


def test_the_notebook_sections_name_their_numerical_tolerance():
    """A bare 1e-9 in a section hides what it is for; the tolerance is one named constant in evaluate.metrics."""
    from halolens.config import repo_root
    from halolens.evaluate.metrics import TOLERANCE_PP
    assert 0 < TOLERANCE_PP < 1e-6
    for name in ("08_forecast_method", "09_backtest", "10_forecast_2026", "11a_uncertainty", "11b_scenarios"):
        source = (repo_root() / "notebook" / "sections" / f"{name}.py").read_text(encoding="utf-8")
        assert "1e-9" not in source, name
    for name in ("10_forecast_2026", "11b_scenarios"):
        assert "TOLERANCE_PP" in (repo_root() / "notebook" / "sections" / f"{name}.py").read_text(encoding="utf-8")


def test_references_file_cites_the_listed_methods_with_links():
    from halolens.config import repo_root
    text = (repo_root() / "docs" / "references.md").read_text(encoding="utf-8")
    assert text.count("http") >= 8
    for author in ("Durbin", "Hyndman", "Efron", "Cameron", "James", "Hastings"):
        assert author in text, author
    for topic in ("state space", "bootstrap", "winsor", "UnobservedComponents"):
        assert topic.lower() in text.lower(), topic
