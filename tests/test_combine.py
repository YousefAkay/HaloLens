"""Tests for the monthly index and the nowcast (forecast.monthly_index, forecast.nowcast). Owner: FCT.

This file is the FCT test file for the forecast pipeline pieces that feed `forecast.combine`; F-05 adds the combine
tests here. Hand-made pairs with exact growth; no CRM data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from leaselens.forecast.asof import make_snapshot
from leaselens.forecast.baselines import frozen_weights, training_pairs
from leaselens.forecast.monthly_index import INDEX_COLUMNS, build_monthly_index
from leaselens.forecast.nowcast import METHOD_LOCAL_TREND, METHOD_TRAILING_MEAN, nowcast
from tests.test_baselines import annual_leases, empty_external, tables_from

CUTOFF = pd.Timestamp("2024-12-31")
FIRST_MONTH = pd.Period("2021-01", freq="M")
N_MONTHS = 48                      # Jan 2021 .. Dec 2024
PAIRS_PER_MONTH = 12               # above nowcast.min_pairs_per_month
BASE_GROWTH = 0.03
ABS_TOL = 1e-9


def monthly_pairs(growth_by_month=None, pairs_per_month: int = PAIRS_PER_MONTH, skip=(), prop_code="aaa"):
    """One segment, `pairs_per_month` pairs in each month; log growth given per month (default constant)."""
    rows = []
    for offset in range(N_MONTHS):
        month = FIRST_MONTH + offset
        if month in skip:
            continue
        growth = BASE_GROWTH if growth_by_month is None else growth_by_month(offset)
        for k in range(pairs_per_month):
            rows.append({"unit_id": f"u{offset}_{k}", "prop_code": prop_code, "beds": 1, "is_renewal": True,
                         "lease_start": month.to_timestamp() + pd.Timedelta(days=14), "loggrowth_net": growth,
                         "loggrowth_contract": growth + 0.01})
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def constant_index(cfg):
    return build_monthly_index(monthly_pairs(), cfg, cutoff=CUTOFF)


# ---------------------------------------------------------------------------
# build_monthly_index
# ---------------------------------------------------------------------------
def test_index_has_one_row_per_month_with_the_agreed_columns(constant_index):
    assert list(constant_index.columns) == INDEX_COLUMNS
    assert len(constant_index) == N_MONTHS
    assert constant_index["month"].iloc[0] == FIRST_MONTH
    assert constant_index["month"].is_monotonic_increasing


def test_thick_months_use_only_their_own_pairs(constant_index):
    assert (constant_index["pool_radius"] == 0).all()
    assert (constant_index["n_pairs_used"] == PAIRS_PER_MONTH).all()


def test_constant_growth_gives_a_constant_index(constant_index):
    assert constant_index["log_net"].tolist() == pytest.approx([BASE_GROWTH] * N_MONTHS)
    assert constant_index["log_contract"].tolist() == pytest.approx([BASE_GROWTH + 0.01] * N_MONTHS)
    assert constant_index["pct_net"].iloc[0] == pytest.approx(100 * np.expm1(BASE_GROWTH))


def test_thin_months_pool_neighbours_until_the_minimum_is_met(cfg):
    thin = build_monthly_index(monthly_pairs(pairs_per_month=4), cfg, cutoff=CUTOFF)
    middle = thin.iloc[N_MONTHS // 2]
    assert middle["n_pairs"] == 4
    assert middle["pool_radius"] == 1                       # 3 months x 4 pairs = 12 >= minimum 10
    assert middle["n_pairs_used"] == 12


def test_pooling_radius_is_capped_and_empty_months_stay_missing(cfg):
    sparse = build_monthly_index(monthly_pairs(pairs_per_month=1), cfg, cutoff=CUTOFF)
    assert (sparse["pool_radius"] <= cfg["nowcast"]["max_pool_months"]).all()
    gap_month = FIRST_MONTH + 10
    with_gap = build_monthly_index(monthly_pairs(skip=[gap_month]), cfg, cutoff=CUTOFF)
    gap_row = with_gap[with_gap["month"] == gap_month].iloc[0]
    assert gap_row["n_pairs"] == 0 and gap_row["pool_radius"] == 1   # borrowed neighbours, so it is not empty
    assert np.isfinite(gap_row["log_net"])


def test_months_with_no_pairs_even_after_pooling_are_nan(cfg):
    radius = cfg["nowcast"]["max_pool_months"]
    skip = [FIRST_MONTH + 20 + step for step in range(2 * radius + 1)]
    index = build_monthly_index(monthly_pairs(skip=skip), cfg, cutoff=CUTOFF)
    center = index[index["month"] == FIRST_MONTH + 20 + radius].iloc[0]
    assert center["n_pairs_used"] == 0 and np.isnan(center["log_net"])


def test_index_uses_fixed_weights_not_the_monthly_mix(cfg):
    """Two segments: aaa grows 10%, bbb 0%. Weights are frozen from the window, so a month dominated by bbb is not."""
    a = monthly_pairs(growth_by_month=lambda m: np.log(1.1), pairs_per_month=9, prop_code="aaa")
    b = monthly_pairs(growth_by_month=lambda m: 0.0, pairs_per_month=3, prop_code="bbb")
    both = pd.concat([a, b], ignore_index=True)
    index = build_monthly_index(both, cfg, cutoff=CUTOFF)
    # frozen weights are 9:3 = 0.75 / 0.25, every month
    assert index["log_net"].tolist() == pytest.approx([0.75 * np.log(1.1)] * N_MONTHS)


def test_index_winsorizes_with_bounds_from_the_given_pairs(cfg):
    pairs = monthly_pairs(pairs_per_month=100)
    pairs.loc[pairs.index[0], "loggrowth_net"] = 50.0       # one absurd pair among 4800
    index = build_monthly_index(pairs, cfg, cutoff=CUTOFF)
    assert index["log_net"].max() < 0.1


def test_index_rejects_empty_input(cfg):
    with pytest.raises(ValueError):
        build_monthly_index(monthly_pairs().iloc[0:0], cfg)


# ---------------------------------------------------------------------------
# nowcast
# ---------------------------------------------------------------------------
def test_constant_series_projects_the_same_level(constant_index, cfg):
    result = nowcast(constant_index, CUTOFF, cfg)
    assert result["method_used"] == METHOD_LOCAL_TREND
    assert result["trend_log_net"] == pytest.approx(BASE_GROWTH, abs=1e-6)
    assert result["year_log_net"] == pytest.approx(BASE_GROWTH, abs=1e-6)
    assert result["year_log_contract"] == pytest.approx(BASE_GROWTH + 0.01, abs=1e-6)
    assert len(result["projection"]) == 12
    assert result["projection"]["month"].iloc[0] == pd.Period("2025-01", freq="M")


def test_rising_series_projects_above_the_last_level_and_damping_limits_it(cfg):
    rising = build_monthly_index(monthly_pairs(growth_by_month=lambda m: 0.01 + 0.0005 * m), cfg, cutoff=CUTOFF)
    undamped = nowcast(rising, CUTOFF, {**cfg, "nowcast": {**cfg["nowcast"], "trend_damping": 1.0}})
    damped = nowcast(rising, CUTOFF, cfg)
    last_level = rising["log_net"].iloc[-1]
    assert damped["year_log_net"] > last_level
    assert undamped["year_log_net"] > damped["year_log_net"]


def test_undamped_projection_continues_a_straight_line(cfg):
    slope = 0.0005
    rising = build_monthly_index(monthly_pairs(growth_by_month=lambda m: 0.01 + slope * m), cfg, cutoff=CUTOFF)
    result = nowcast(rising, CUTOFF, {**cfg, "nowcast": {**cfg["nowcast"], "trend_damping": 1.0}})
    steps = np.arange(1, 13)
    expected = rising["log_net"].iloc[-1] + slope * steps
    assert result["projection"]["log_net"].to_numpy() == pytest.approx(expected, abs=2e-4)


def test_short_history_falls_back_to_the_trailing_mean_and_says_why(cfg):
    short = build_monthly_index(monthly_pairs().iloc[: PAIRS_PER_MONTH * 18], cfg, cutoff=CUTOFF)
    result = nowcast(short, pd.Timestamp("2022-06-30"), cfg)
    assert result["method_used"] == METHOD_TRAILING_MEAN
    assert "observed months" in result["fallback_reason"]
    assert result["year_log_net"] == pytest.approx(BASE_GROWTH)


def test_trailing_mean_method_is_config_driven(constant_index, cfg):
    forced = {**cfg, "nowcast": {**cfg["nowcast"], "method": "trailing_mean"}}
    result = nowcast(constant_index, CUTOFF, forced)
    assert result["method_used"] == METHOD_TRAILING_MEAN
    assert result["year_log_net"] == pytest.approx(BASE_GROWTH)


def test_year_projection_weights_months_by_calendar_pair_share(cfg):
    """Pairs only in July: the year value is the July projection, not the average of the twelve months."""
    july_only = monthly_pairs(growth_by_month=lambda m: 0.01 + 0.0005 * m)
    july_only = july_only[july_only["lease_start"].dt.month == 7]
    index = build_monthly_index(july_only, cfg, cutoff=CUTOFF)
    forced = {**cfg, "nowcast": {**cfg["nowcast"], "method": "trailing_mean", "fallback_window_months": 1}}
    result = nowcast(index, CUTOFF, forced)
    assert result["year_log_net"] == pytest.approx(result["projection"]["log_net"].iloc[0])


def test_nowcast_ignores_months_after_the_cutoff(constant_index, cfg):
    later = constant_index.copy()
    extra = later.tail(6).assign(month=later["month"].tail(6) + 6, log_net=9.0, log_contract=9.0)
    result = nowcast(pd.concat([later, extra], ignore_index=True), CUTOFF, cfg)
    assert result["year_log_net"] == pytest.approx(BASE_GROWTH, abs=1e-6)


def test_pipeline_ignores_leases_starting_after_the_cutoff(cfg):
    """Snapshot -> pairs -> index -> nowcast gives the same answer with or without 2025 leases."""
    tables = tables_from(annual_leases())
    truncated = tables_from(tables.leases[tables.leases["lease_start"] <= CUTOFF])

    def run(source):
        pairs = training_pairs(make_snapshot(source, empty_external(), CUTOFF), cfg)
        loose = {**cfg, "nowcast": {**cfg["nowcast"], "min_pairs_per_month": 2}}
        return nowcast(build_monthly_index(pairs, loose, cutoff=CUTOFF), CUTOFF, loose)

    assert run(tables)["year_log_net"] == run(truncated)["year_log_net"]


def test_index_and_nowcast_run_on_the_synthetic_fixtures(raw, cfg):
    """Smoke test on the committed synthetic fixtures (aggregates only)."""
    from leaselens.io import canonicalize
    snapshot = make_snapshot(canonicalize(raw), empty_external(), CUTOFF)
    pairs = training_pairs(snapshot, cfg)
    weights = frozen_weights(pairs, CUTOFF, cfg)
    assert weights["weight"].sum() == pytest.approx(1.0)
    index = build_monthly_index(pairs, cfg, cutoff=CUTOFF)
    result = nowcast(index, CUTOFF, cfg)
    assert np.isfinite(result["year_log_net"]) and np.isfinite(result["year_log_contract"])
    assert result["months_observed"] > 0


# ---------------------------------------------------------------------------
# forecast (F-05): renewal + turnover + incentive engines, fixed-weight aggregation
# ---------------------------------------------------------------------------
UNITS_PER_PROP = 6                      # above incentives.min_leases_per_cell and combine.min_pairs_history
CONSTANT_GROWTH = {year: 0.03 for year in range(2020, 2026)}
ENGINE_UNITS = [(prop, province, f"{index:04d}") for prop, province in (("aaa", "QC"), ("bbb", "ON"))
                for index in range(UNITS_PER_PROP)]


def engine_tables(growth=CONSTANT_GROWTH, discount_by_year=None, renewal=True):
    leases = annual_leases(growth, units=ENGINE_UNITS)
    leases["is_renewal"] = renewal
    if discount_by_year is not None:
        discount = leases["lease_start"].dt.year.map(discount_by_year).fillna(0.0)
        leases["rent_net_all_incentives"] = leases["rent_contract"] * (1 - discount)
        leases["has_concession"] = discount > 0
    return tables_from(leases)


def run_forecast(tables, cfg, cutoff=CUTOFF):
    from leaselens.forecast.combine import forecast
    return forecast(make_snapshot(tables, empty_external(), cutoff), cfg)


def test_weighted_median_follows_the_weights():
    from leaselens.forecast.combine import weighted_median
    values = pd.Series([1.0, 2.0, 3.0])
    assert weighted_median(values, pd.Series([1.0, 1.0, 1.0])) == 2.0
    assert weighted_median(values, pd.Series([0.1, 0.1, 0.8])) == 3.0
    assert weighted_median(values, pd.Series([0.8, 0.1, 0.1])) == 1.0


def test_constant_growth_and_no_discounts_forecast_that_growth(cfg):
    result = run_forecast(engine_tables(), cfg)
    assert result.model_name == "E1_engine_blend" and result.target_year == 2025
    assert result.headline_contract_pct == pytest.approx(100 * np.expm1(np.log1p(0.03)), abs=0.1)
    assert result.headline_net_pct == pytest.approx(result.headline_contract_pct)
    assert result.median_net_pct == pytest.approx(result.headline_net_pct, abs=1e-6)
    assert result.assumptions


def test_segment_table_has_weights_components_and_discounts(cfg):
    result = run_forecast(engine_tables(), cfg)
    segments = result.segments
    assert segments["weight"].sum() == pytest.approx(1.0)
    assert {"hist_contract", "signal_contract", "nowcast_contract", "g_contract", "d0", "d1", "g_net"} <= set(segments.columns)
    assert segments["g_contract"].notna().all() and segments["g_net"].notna().all()


def test_headline_is_the_fixed_weight_aggregate_of_segment_forecasts(cfg):
    """aaa grows 10% a year, bbb 0%; the headline is the weighted mean on the log scale."""
    fast = annual_leases({year: 0.10 for year in range(2020, 2026)}, units=[u for u in ENGINE_UNITS if u[0] == "aaa"])
    flat = annual_leases({year: 0.0 for year in range(2020, 2026)}, units=[u for u in ENGINE_UNITS if u[0] == "bbb"])
    result = run_forecast(tables_from(pd.concat([fast, flat], ignore_index=True)), cfg)
    segments = result.segments
    expected = float((segments["weight"] * segments["g_contract"]).sum())
    assert result.headline_contract_pct == pytest.approx(100 * np.expm1(expected))
    by_prop = segments.set_index("prop_code")["g_contract"]
    assert by_prop["aaa"] > 0.05 > by_prop["bbb"] + 0.0   # each segment keeps its own history


def test_rising_discounts_pull_net_growth_below_contract_growth(cfg):
    """Discount 0 until 2023 and 5% in 2024: d0 = 5%, trend d1 = 10%, so net sits below contract."""
    result = run_forecast(engine_tables(discount_by_year={2024: 0.05}), cfg)
    expected_gap = 100 * (np.expm1(np.log1p(0.03) + np.log(0.90) - np.log(0.95)) - 0.03)
    assert result.headline_net_pct < result.headline_contract_pct
    assert result.headline_net_pct - result.headline_contract_pct == pytest.approx(expected_gap, abs=0.1)


def test_turnover_segments_without_asking_data_use_history_and_nowcast_only(cfg):
    result = run_forecast(engine_tables(renewal=False), cfg)
    segments = result.segments
    assert segments["signal_contract"].isna().all()
    assert segments["g_contract"].notna().all()
    assert result.headline_contract_pct == pytest.approx(100 * np.expm1(np.log1p(0.03)), abs=0.1)


def test_forecast_ignores_leases_that_start_after_the_cutoff(cfg):
    tables = engine_tables()
    truncated = tables_from(tables.leases[tables.leases["lease_start"] <= CUTOFF])
    full, early = run_forecast(tables, cfg), run_forecast(truncated, cfg)
    assert full.headline_net_pct == early.headline_net_pct
    assert full.headline_contract_pct == early.headline_contract_pct


def test_forecast_reports_where_each_component_came_from(cfg):
    result = run_forecast(engine_tables(), cfg)
    assert result.components["history_sources"] == {"segment": len(result.segments)}
    assert result.components["n_segments"] == len(result.segments)
    assert "year_log_contract" in result.components["nowcast"]


def test_forecast_runs_on_the_synthetic_fixtures_at_every_backtest_fold(raw, cfg):
    from leaselens.config import cutoff_for
    from leaselens.io import canonicalize
    synthetic = canonicalize(raw)
    for year in cfg["forecast_years"]["backtest_years"] + [cfg["forecast_years"]["target_year"]]:
        result = run_forecast(synthetic, cfg, cutoff_for(year, cfg))
        assert np.isfinite(result.headline_net_pct) and np.isfinite(result.headline_contract_pct)
        assert result.target_year == year
