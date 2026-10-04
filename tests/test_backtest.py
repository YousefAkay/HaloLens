"""Tests for error metrics and the backtest skeleton (evaluate.metrics, evaluate.backtest). Owner: FCT.

Uses the same hand-made leases as test_baselines (known yearly growth). `run_backtest` uses
`forecast.combine.forecast` (F-05).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from leaselens.evaluate.backtest import (actual_for_year, backtest_all_models, backtest_baselines, run_backtest,
                                         summarize_models)
from leaselens.evaluate.metrics import absolute_error_pp, mean_absolute_error_pp, signed_error_pp
from leaselens.forecast.asof import make_snapshot
from leaselens.forecast.baselines import BASELINES, frozen_weights, training_pairs
from leaselens.config import cutoff_for
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
    from leaselens.io import canonicalize
    result = backtest_baselines(canonicalize(raw), empty_external(), cfg)
    assert result[result["model"] != "B2_market_anchor"]["error_pp_net"].notna().any()


def test_run_backtest_uses_the_same_forecast_as_the_engine_pipeline(raw, cfg):
    """backtest() must call the very forecast() behind estimate_2026(): same snapshot, same numbers."""
    from leaselens.forecast.combine import forecast
    from leaselens.io import canonicalize
    synthetic = canonicalize(raw)
    fold = run_backtest(synthetic, empty_external(), 2025, cfg)
    direct = forecast(make_snapshot(synthetic, empty_external(), cutoff_for(2025, cfg)), cfg)
    assert fold.forecast.headline_net_pct == direct.headline_net_pct
    assert fold.error_pp_net == pytest.approx(direct.headline_net_pct - fold.actual_net_pct)
    assert fold.target_year == 2025 and fold.coverage["n_pairs_actual"] > 0


def test_all_models_table_adds_the_engine_to_the_baselines(raw, cfg):
    from leaselens.io import canonicalize
    table = backtest_all_models(canonicalize(raw), empty_external(), cfg)
    assert set(table["model"]) == set(BASELINES) | {"E1_engine_blend"}
    engine = table[table["model"] == "E1_engine_blend"]
    assert engine["forecast_net_pct"].notna().all() and engine["note"].eq("").all()


def test_model_summary_separates_selection_years_from_the_holdout(raw, cfg):
    from leaselens.io import canonicalize
    table = backtest_all_models(canonicalize(raw), empty_external(), cfg)
    summary = summarize_models(table, cfg).set_index("model")
    engine = table[table["model"] == "E1_engine_blend"].set_index("year")["abs_error_pp_net"]
    selection = cfg["forecast_years"]["selection_years"]
    assert summary.loc["E1_engine_blend", "mae_selection_pp"] == pytest.approx(engine.loc[selection].mean())
    assert summary.loc["E1_engine_blend", "mae_holdout_pp"] == pytest.approx(engine.loc[cfg["forecast_years"]["holdout_year"]])
    assert summary.loc["E1_engine_blend", "n_folds_run"] == len(engine)
    assert summary.loc["B2_market_anchor", "n_folds_run"] == 0   # no external data in this fixture
