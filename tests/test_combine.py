"""Tests for the monthly index and the nowcast (forecast.monthly_index, forecast.nowcast). Owner: FCT.

This file is the FCT test file for the forecast pipeline pieces that feed `forecast.combine`; F-05 adds the combine
tests here. Hand-made pairs with exact growth; no CRM data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from halolens.forecast.asof import make_snapshot
from halolens.forecast.baselines import frozen_weights, training_pairs
from halolens.forecast.monthly_index import INDEX_COLUMNS, build_monthly_index
from halolens.forecast.nowcast import METHOD_LOCAL_TREND, METHOD_TRAILING_MEAN, nowcast
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
    from halolens.io import canonicalize
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
    from halolens.forecast.combine import forecast
    return forecast(make_snapshot(tables, empty_external(), cutoff), cfg)


def test_weighted_median_follows_the_weights():
    from halolens.forecast.combine import weighted_median
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
    from halolens.config import cutoff_for
    from halolens.io import canonicalize
    synthetic = canonicalize(raw)
    for year in cfg["forecast_years"]["backtest_years"] + [cfg["forecast_years"]["target_year"]]:
        result = run_forecast(synthetic, cfg, cutoff_for(year, cfg))
        assert np.isfinite(result.headline_net_pct) and np.isfinite(result.headline_contract_pct)
        assert result.target_year == year


# ---------------------------------------------------------------------------
# E2_regulated: Québec renewals anchored on the TAL percentage; Ontario (new-build property) exempt unless the guideline applies
# ---------------------------------------------------------------------------
from tests.test_baselines import GUIDELINE_PCT, TAL_PCT, regulated_rows   # noqa: E402

PERCENT_OF_RATE = 100


def run_regulated(tables, cfg, strict=False, ontario_newbuild_guideline_applies=False, external=None):
    from halolens.forecast.asof import snapshot_for_year
    from halolens.forecast.combine import forecast_regulated
    external = regulated_rows() if external is None else external
    snapshot = snapshot_for_year(tables, external, 2025, cfg, strict=strict)
    return forecast_regulated(snapshot, cfg, ontario_newbuild_guideline_applies=ontario_newbuild_guideline_applies)


def qc_gap() -> float:
    return float(np.mean([np.log1p(CONSTANT_GROWTH[y]) - np.log1p(TAL_PCT[y] / PERCENT_OF_RATE) for y in (2022, 2023, 2024)]))


def test_qc_renewals_are_anchored_on_the_target_years_tal_rate_plus_the_training_gap(cfg):
    result = run_regulated(engine_tables(), cfg)
    segments = result.segments.set_index("prop_code")
    expected = np.log1p(TAL_PCT[2025] / PERCENT_OF_RATE) + qc_gap()
    assert result.model_name == "E2_regulated"
    assert segments.loc["aaa", "g_contract"] == pytest.approx(expected, abs=2e-3)
    assert segments.loc["aaa", "g_source"] == "tal_anchor"
    anchor = result.components["regulatory_anchors"]["QC"]
    assert anchor["rate_year"] == 2025 and anchor["rate_pct"] == pytest.approx(TAL_PCT[2025]) and anchor["gap_years"] == [2022, 2023, 2024]


def test_ontario_renewals_keep_the_e1_blend_in_the_central_scenario(cfg):
    e1 = run_forecast(engine_tables(), cfg)
    e2 = run_regulated(engine_tables(), cfg)
    on_e1 = e1.segments.set_index("prop_code").loc["bbb", "g_contract"]
    on_e2 = e2.segments.set_index("prop_code").loc["bbb"]
    assert on_e2["g_source"] == "blend" and on_e2["g_contract"] == pytest.approx(on_e1)


def test_newbuild_guideline_scenario_anchors_ontario_renewals_on_the_guideline_plus_its_gap(cfg):
    central = run_regulated(engine_tables(), cfg)
    alternative = run_regulated(engine_tables(), cfg, ontario_newbuild_guideline_applies=True)
    gap = np.log1p(CONSTANT_GROWTH[2024]) - np.log1p(GUIDELINE_PCT[2024] / PERCENT_OF_RATE)
    expected = np.log1p(GUIDELINE_PCT[2025] / PERCENT_OF_RATE) + gap
    on_alt = alternative.segments.set_index("prop_code").loc["bbb"]
    assert on_alt["g_source"] == "guideline_anchor" and on_alt["g_contract"] == pytest.approx(expected, abs=2e-3)
    assert alternative.headline_contract_pct < central.headline_contract_pct          # guideline 1.5% < history 3%
    # the central result already carries the alternative's number for the scenario table
    assert central.segments.set_index("prop_code").loc["bbb", "g_contract_alt"] == pytest.approx(on_alt["g_contract"])


def test_strict_rule_falls_back_to_the_latest_released_tal_year(cfg):
    jan31 = run_regulated(engine_tables(), cfg)
    strict = run_regulated(engine_tables(), cfg, strict=True)
    assert strict.components["regulatory_anchors"]["QC"]["rate_year"] == 2024     # the 2025 rate came out Jan 15, 2025
    assert strict.headline_contract_pct != jan31.headline_contract_pct


def test_turnovers_and_the_incentive_engine_are_identical_to_e1(cfg):
    leases = pd.concat([annual_leases(CONSTANT_GROWTH, units=ENGINE_UNITS).assign(is_renewal=True),
                        annual_leases(CONSTANT_GROWTH, units=[("ccc", "QC", f"{i:04d}") for i in range(UNITS_PER_PROP)])
                        .assign(is_renewal=False)], ignore_index=True)
    tables = tables_from(leases)
    from halolens.forecast.asof import snapshot_for_year
    from halolens.forecast.combine import forecast
    snapshot = snapshot_for_year(tables, regulated_rows(), 2025, cfg)
    e1, e2 = forecast(snapshot, cfg).segments, run_regulated(tables, cfg).segments
    turnover = ~e1["is_renewal"].astype(bool)
    pd.testing.assert_frame_equal(e1.loc[turnover, ["prop_code", "g_contract", "d0", "d1", "g_net"]].reset_index(drop=True),
                                  e2.loc[turnover, ["prop_code", "g_contract", "d0", "d1", "g_net"]].reset_index(drop=True))


def test_e2_needs_a_released_tal_rate(cfg):
    with pytest.raises(ValueError, match="rate"):
        run_regulated(engine_tables(), cfg, external=empty_external())


def test_e2_ignores_leases_and_rates_after_the_cutoffs(cfg):
    tables = engine_tables()
    truncated = tables_from(tables.leases[tables.leases["lease_start"] <= CUTOFF])
    later = pd.concat([regulated_rows(), regulated_rows(tal={2025: 50.0}).assign(
        release_date=pd.Timestamp("2025-03-01"))], ignore_index=True)       # after the Jan-31 window
    base = run_regulated(tables, cfg)
    assert run_regulated(truncated, cfg, external=later).headline_net_pct == base.headline_net_pct


def test_e2_without_ontario_segments_does_not_need_the_guideline(cfg):
    qc_only = tables_from(annual_leases(CONSTANT_GROWTH, units=[u for u in ENGINE_UNITS if u[1] == "QC"]))
    result = run_regulated(qc_only, cfg, external=regulated_rows(guideline={}))
    assert "ON" not in result.components["regulatory_anchors"]
    assert result.segments["g_contract_alt"].notna().all()


# ---------------------------------------------------------------------------
# Scenarios and per building x beds forecasts
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def regulated_result(cfg):
    """E2 on hand-made leases with discounts of 3% (2023) and 5% (2024): d0 = 5%, trend d1 = 7%."""
    return run_regulated(engine_tables(discount_by_year={2023: 0.03, 2024: 0.05}), cfg)


def row_of(table: pd.DataFrame, name: str) -> pd.Series:
    return table.set_index("scenario").loc[name]


def test_central_scenario_equals_the_forecast_headline(regulated_result, cfg):
    from halolens.forecast.scenarios import SCENARIO_COLUMNS, scenario_table
    table = scenario_table(regulated_result, cfg)
    assert list(table.columns) == SCENARIO_COLUMNS
    central = row_of(table, "central")
    assert central["headline_net_pct"] == pytest.approx(regulated_result.headline_net_pct)
    assert central["headline_contract_pct"] == pytest.approx(regulated_result.headline_contract_pct)
    assert central["delta_net_pp"] == pytest.approx(0.0)


def test_deeper_incentives_lower_net_growth_and_leave_contract_growth_alone(regulated_result, cfg):
    from halolens.forecast.scenarios import scenario_table
    table = scenario_table(regulated_result, cfg)
    deeper, shallower, central = (row_of(table, n) for n in ("incentives_deeper", "incentives_shallower", "central"))
    assert deeper["headline_net_pct"] < central["headline_net_pct"] < shallower["headline_net_pct"]
    assert deeper["headline_contract_pct"] == pytest.approx(central["headline_contract_pct"])


def test_renewal_mix_scenarios_move_toward_the_segment_with_more_growth(regulated_result, cfg):
    from halolens.forecast.scenarios import scenario_table
    segments = regulated_result.segments
    renewals_grow_more = (segments.loc[segments["is_renewal"], "g_contract"].mean()
                          > segments.loc[~segments["is_renewal"], "g_contract"].mean())
    table = scenario_table(regulated_result, cfg)
    more, fewer = row_of(table, "more_renewals"), row_of(table, "fewer_renewals")
    if segments["is_renewal"].all():                       # only renewals in the fixture: the mix cannot move
        assert more["headline_net_pct"] == pytest.approx(fewer["headline_net_pct"])
    else:
        assert (more["headline_net_pct"] > fewer["headline_net_pct"]) == renewals_grow_more


def test_reweighting_keeps_the_weights_summing_to_one_and_stays_in_bounds():
    from halolens.forecast.scenarios import _reweight
    weights = pd.Series([0.3, 0.3, 0.2, 0.2])
    is_renewal = pd.Series([True, True, False, False])
    for shift in (-0.05, 0.0, 0.05, 0.9, -0.9):
        moved = _reweight(weights, is_renewal, shift)
        assert moved.sum() == pytest.approx(1.0) and (moved >= 0).all()
    assert _reweight(weights, is_renewal, 0.1)[is_renewal].sum() == pytest.approx(0.7)
    assert _reweight(weights, pd.Series([True] * 4), 0.1).equals(weights)


def test_shallower_incentives_cannot_push_the_discount_below_zero(cfg):
    from halolens.forecast.scenarios import scenario_table
    table = scenario_table(run_regulated(engine_tables(), cfg), cfg)          # no discounts at all: d1 = 0 already
    assert row_of(table, "incentives_shallower")["headline_net_pct"] == pytest.approx(row_of(table, "central")["headline_net_pct"])
    assert row_of(table, "incentives_deeper")["headline_net_pct"] < row_of(table, "central")["headline_net_pct"]


def test_newbuild_scenario_matches_the_alternative_forecast(regulated_result, cfg):
    from halolens.forecast.scenarios import scenario_table
    alternative = run_regulated(engine_tables(discount_by_year={2023: 0.03, 2024: 0.05}), cfg, ontario_newbuild_guideline_applies=True)
    table = scenario_table(regulated_result, cfg)
    assert row_of(table, "ontario_newbuild_guideline_applies")["headline_net_pct"] == pytest.approx(alternative.headline_net_pct)
    assert row_of(table, "ontario_newbuild_guideline_applies")["headline_net_pct"] < row_of(table, "central")["headline_net_pct"]


def test_low_and_high_bracket_the_central_and_every_single_lever(regulated_result, cfg):
    from halolens.forecast.scenarios import scenario_table
    table = scenario_table(regulated_result, cfg).set_index("scenario")
    assert table.loc["low", "headline_net_pct"] <= table["headline_net_pct"].drop(["low", "high"]).min() + 1e-9
    assert table.loc["high", "headline_net_pct"] >= table["headline_net_pct"].drop(["low", "high"]).max() - 1e-9
    assert table.loc["low", "headline_net_pct"] < table.loc["central", "headline_net_pct"] < table.loc["high", "headline_net_pct"]
    assert table.loc["low", "delta_net_pp"] < 0 < table.loc["high", "delta_net_pp"]


def test_scenarios_on_an_e1_result_leave_the_newbuild_rows_empty_but_still_give_low_and_high(cfg):
    from halolens.forecast.scenarios import scenario_table
    table = scenario_table(run_forecast(engine_tables(), cfg), cfg).set_index("scenario")
    assert np.isnan(table.loc["ontario_newbuild_guideline_applies", "headline_net_pct"])
    assert np.isfinite(table.loc["low", "headline_net_pct"]) and not table.loc["low", "ontario_newbuild_guideline_applies"]


def test_incentive_shift_is_capped_at_the_maximum_discount_share(regulated_result, cfg):
    from halolens.forecast.scenarios import evaluate_scenario
    huge = evaluate_scenario(regulated_result.segments, cfg, incentive_shift_pp=1000.0)
    capped_d1 = cfg["incentives"]["max_discount_share"]
    segments = regulated_result.segments
    expected = (segments["weight"] * (segments["g_contract"] + np.log1p(-capped_d1) - np.log1p(-segments["d0"]))).sum()
    assert huge["headline_net_pct"] == pytest.approx(100 * np.expm1(expected))


def test_building_beds_forecast_has_one_row_per_cell_and_unit_weights(regulated_result, cfg):
    from halolens.forecast.scenarios import building_beds_forecast
    table = building_beds_forecast(regulated_result, cfg)
    assert len(table) == regulated_result.segments[["prop_code", "beds"]].drop_duplicates().shape[0]
    assert table["weight"].sum() == pytest.approx(1.0)
    assert {"net_pct_raw", "net_pct_shrunk", "contract_pct_raw", "contract_pct_shrunk", "building_net_pct"} <= set(table.columns)


def test_shrinkage_pulls_thin_cells_toward_the_building_mean_and_leaves_thick_cells_alone(cfg):
    from halolens.forecast.scenarios import building_beds_forecast
    from halolens.contracts import ForecastResult
    segments = pd.DataFrame({"prop_code": ["aaa", "aaa", "aaa"], "beds": [1, 2, 3], "is_renewal": [True, True, True],
                             "weight": [0.5, 0.25, 0.25], "n_pairs_window": [1000, 1, 0],
                             "g_net": [0.02, 0.10, 0.10], "g_contract": [0.02, 0.10, 0.10]})
    result = ForecastResult(2025, CUTOFF, 0, 0, 0, 0, segments)
    table = building_beds_forecast(result, cfg).set_index("beds")
    building_log = 0.5 * 0.02 + 0.25 * 0.10 + 0.25 * 0.10
    assert table.loc[1, "net_pct_shrunk"] == pytest.approx(table.loc[1, "net_pct_raw"], abs=0.1)       # n = 1000: ~raw
    assert table.loc[3, "net_pct_shrunk"] == pytest.approx(100 * np.expm1(building_log))               # n = 0: the building mean
    assert table.loc[2, "net_pct_raw"] > table.loc[2, "net_pct_shrunk"] > table.loc[2, "building_net_pct"]


def test_regulated_forecast_runs_when_the_synthetic_fixtures_get_tal_rows(raw, cfg):
    """Smoke test: E2, its scenarios and the building table on the committed synthetic fixtures (aggregates only)."""
    from halolens.forecast.asof import snapshot_for_year
    from halolens.forecast.combine import forecast_regulated
    from halolens.forecast.scenarios import building_beds_forecast, scenario_table
    from halolens.io import canonicalize
    tal = {year: 2.0 for year in range(2019, 2027)}
    guideline = {year: 2.5 for year in range(2019, 2027)}
    snapshot = snapshot_for_year(canonicalize(raw), regulated_rows(tal, guideline), 2025, cfg)
    result = forecast_regulated(snapshot, cfg)
    assert np.isfinite(result.headline_net_pct)
    assert scenario_table(result, cfg)["headline_net_pct"].notna().sum() >= 7
    assert building_beds_forecast(result, cfg)["net_pct_shrunk"].notna().all()


# ---------------------------------------------------------------------------
# Headline split by province
# ---------------------------------------------------------------------------
def province_map(tables) -> pd.Series:
    return tables.leases.drop_duplicates("prop_code").set_index("prop_code")["province"]


def test_province_split_covers_every_province_and_repeats_the_headline(cfg):
    from halolens.forecast.baselines import last_year
    from halolens.forecast.scenarios import headline_by_province
    tables = engine_tables()
    result = last_year(make_snapshot(tables, empty_external(), CUTOFF), cfg)
    split = headline_by_province(result, province_map(tables)).set_index("province")
    assert set(split.index) == {"QC", "ON", "all"}
    assert split.loc[["QC", "ON"], "weight_share"].sum() == pytest.approx(1.0)
    assert split.loc["all", "net_pct"] == pytest.approx(result.headline_net_pct)
    assert split.loc["all", "contract_pct"] == pytest.approx(result.headline_contract_pct)


def test_province_split_gives_each_province_its_own_growth(cfg):
    from halolens.forecast.baselines import last_year
    from halolens.forecast.scenarios import headline_by_province
    fast = annual_leases({year: 0.10 for year in range(2020, 2026)}, units=[u for u in ENGINE_UNITS if u[0] == "aaa"])
    flat = annual_leases({year: 0.0 for year in range(2020, 2026)}, units=[u for u in ENGINE_UNITS if u[0] == "bbb"])
    tables = tables_from(pd.concat([fast, flat], ignore_index=True))
    result = last_year(make_snapshot(tables, empty_external(), CUTOFF), cfg)
    split = headline_by_province(result, province_map(tables)).set_index("province")
    assert split.loc["QC", "net_pct"] == pytest.approx(10.0, abs=0.1)        # aaa is the Québec building
    assert split.loc["ON", "net_pct"] == pytest.approx(0.0, abs=0.1)
    assert split.loc["QC", "weight_share"] == pytest.approx(0.5)


def test_province_split_works_on_engine_results_too(cfg):
    from halolens.forecast.scenarios import headline_by_province
    tables = engine_tables()
    result = run_forecast(tables, cfg)
    split = headline_by_province(result, province_map(tables)).set_index("province")
    assert split.loc["all", "net_pct"] == pytest.approx(result.headline_net_pct)


# ---------------------------------------------------------------------------
# Sensitivity of the headline to one assumption at a time (F-10)
# ---------------------------------------------------------------------------
def sensitivity_inputs(cfg, discounts=True):
    tables = engine_tables(discount_by_year={2023: 0.03, 2024: 0.05} if discounts else None)
    return tables, regulated_rows()


def run_sensitivity(cfg, champion="B0_last_year", external=None):
    from halolens.forecast.scenarios import sensitivity_table
    tables, regulated = sensitivity_inputs(cfg)
    return sensitivity_table(tables, regulated if external is None else external, cfg, champion=champion, year=2025)


def test_sensitivity_table_lists_one_row_per_variant_sorted_by_absolute_change(cfg):
    from halolens.forecast.scenarios import SENSITIVITY_COLUMNS
    table = run_sensitivity(cfg)
    assert list(table.columns) == SENSITIVITY_COLUMNS
    assert table["abs_delta_pp"].dropna().is_monotonic_decreasing
    assert not table.duplicated(["assumption", "variant", "setting", "model"]).any()
    expected_groups = {"information_rule", "gap_bounds", "winsorization", "weight_window", "newbuild_applicability",
                       "incentive_intensity", "renewal_mix", "model_choice"}
    assert set(table["assumption"]) == expected_groups
    assert (table["delta_pp"].abs() - table["abs_delta_pp"]).abs().max() < 1e-12


def test_each_row_is_the_variant_minus_the_base_of_the_same_model(cfg):
    table = run_sensitivity(cfg).dropna(subset=["headline_net_pct"])
    assert ((table["headline_net_pct"] - table["base_net_pct"]) - table["delta_pp"]).abs().max() < 1e-9
    champion_rows = table[(table["model"] == "B0_last_year") & (table["assumption"] != "model_choice")]
    assert champion_rows["base_net_pct"].nunique() == 1            # one champion base for all champion rows


def test_a_variant_changes_exactly_one_key_and_matches_a_manual_rerun(cfg):
    from halolens.forecast.asof import snapshot_for_year
    from halolens.forecast.baselines import last_year
    tables, regulated = sensitivity_inputs(cfg)
    table = run_sensitivity(cfg)
    shorter = {**cfg, "headline": {**cfg["headline"], "weight_window_years": cfg["headline"]["weight_window_years"] - 1}}
    expected = last_year(snapshot_for_year(tables, regulated, 2025, shorter), shorter).headline_net_pct
    row = table[(table["assumption"] == "weight_window")
                & (table["setting"] == str(cfg["headline"]["weight_window_years"] - 1))].iloc[0]
    assert row["headline_net_pct"] == pytest.approx(expected)


def test_the_input_config_is_never_modified(cfg):
    import copy
    before = copy.deepcopy(cfg)
    run_sensitivity(cfg)
    assert cfg == before


def test_information_rule_cannot_move_a_model_that_ignores_public_data_but_moves_e2(cfg):
    table = run_sensitivity(cfg)
    rule = table[table["assumption"] == "information_rule"].set_index("model")
    assert rule.loc["B0_last_year", "delta_pp"] == pytest.approx(0.0)
    assert abs(rule.loc["E2_regulated", "delta_pp"]) > 0                 # the TAL rate of the target year comes out in January


def test_regulatory_levers_are_the_e2_scenario_deltas(cfg):
    from halolens.forecast.scenarios import scenario_table
    table = run_sensitivity(cfg).set_index("variant")
    tables, regulated = sensitivity_inputs(cfg)
    scenarios = scenario_table(run_regulated(tables, cfg), cfg).set_index("scenario")
    for variant in ("ontario_newbuild_guideline_applies", "incentives_deeper", "incentives_shallower", "more_renewals", "fewer_renewals"):
        assert table.loc[variant, "delta_pp"] == pytest.approx(scenarios.loc[variant, "delta_net_pp"])
        assert table.loc[variant, "model"] == "E2_regulated"


def test_model_choice_rows_compare_each_model_with_the_champion(cfg):
    from halolens.forecast.asof import snapshot_for_year
    from halolens.forecast.baselines import trailing_mean
    tables, regulated = sensitivity_inputs(cfg)
    table = run_sensitivity(cfg).set_index("variant")
    direct = trailing_mean(snapshot_for_year(tables, regulated, 2025, cfg), cfg).headline_net_pct
    assert table.loc["B1_trailing_mean", "headline_net_pct"] == pytest.approx(direct)
    assert table.loc["B1_trailing_mean", "delta_pp"] == pytest.approx(direct - table.loc["B1_trailing_mean", "base_net_pct"])
    assert "B0_last_year" not in table.index                              # the champion is not compared with itself


def test_a_champion_that_is_e2_adds_no_duplicate_information_rule_row(cfg):
    table = run_sensitivity(cfg, champion="E2_regulated")
    assert (table[table["assumption"] == "information_rule"]["model"] == "E2_regulated").all()
    assert len(table[table["assumption"] == "information_rule"]) == 1


def test_variants_that_cannot_run_keep_their_row_with_the_reason(cfg):
    table = run_sensitivity(cfg, external=empty_external())
    e2_rows = table[table["model"] == "E2_regulated"]
    assert len(e2_rows) > 0 and e2_rows["headline_net_pct"].isna().all() and e2_rows["note"].ne("").all()
    assert table[table["model"] == "B0_last_year"]["headline_net_pct"].notna().any()   # champion variants still run
    assert table["abs_delta_pp"].isna().iloc[-len(e2_rows):].all()


def test_sensitivity_table_runs_on_the_synthetic_fixtures_with_the_champion_pipeline(raw, cfg):
    from halolens.forecast.scenarios import sensitivity_table
    from halolens.io import canonicalize
    table = sensitivity_table(canonicalize(raw), regulated_rows({y: 2.0 for y in range(2019, 2027)},
                                                                {y: 2.5 for y in range(2019, 2027)}), cfg)
    assert len(table) > 10 and table["delta_pp"].notna().sum() > 5


# ---------------------------------------------------------------------------
# Province split for every model (a champion without segment forecasts must not crash anything downstream)
# ---------------------------------------------------------------------------
PORTFOLIO_ONLY_MODELS = {"B1_trailing_mean", "B2_market_anchor", "B3_tal_anchor"}   # no per-segment forecast


def snapshot_for_every_model(cfg):
    from halolens.forecast.asof import snapshot_for_year
    from tests.test_baselines import market_rows
    tables = engine_tables(discount_by_year={2023: 0.03, 2024: 0.05})
    return tables, snapshot_for_year(tables, market_rows(), 2025, cfg)


@pytest.mark.parametrize("model", ["B0_last_year", "B1_trailing_mean", "B2_market_anchor", "B3_tal_anchor",
                                   "E1_engine_blend", "E2_regulated"])
def test_province_split_works_for_every_model(model, cfg):
    from halolens.evaluate.backtest import all_models
    from halolens.forecast.scenarios import PROVINCE_COLUMNS, headline_by_province
    tables, snapshot = snapshot_for_every_model(cfg)
    result = all_models()[model](snapshot, cfg)
    split = headline_by_province(result, province_map(tables))
    assert list(split.columns) == PROVINCE_COLUMNS
    assert split.iloc[-1]["province"] == "all"
    if model in PORTFOLIO_ONLY_MODELS:
        assert list(split["province"]) == ["all"]                          # no honest split exists for these models
        assert split.loc[0, "weight_share"] == 1.0
        assert split.loc[0, "net_pct"] == pytest.approx(result.headline_net_pct)
        assert split.loc[0, "contract_pct"] == pytest.approx(result.headline_contract_pct)
    else:
        assert list(split["province"]) == ["ON", "QC", "all"]
        assert split.loc[split["province"] == "all", "net_pct"].iloc[0] == pytest.approx(result.headline_net_pct)


def test_the_fallback_row_counts_the_segments_of_the_model(cfg):
    from halolens.forecast.baselines import trailing_mean
    from halolens.forecast.scenarios import headline_by_province
    tables, snapshot = snapshot_for_every_model(cfg)
    result = trailing_mean(snapshot, cfg)
    assert headline_by_province(result, province_map(tables)).loc[0, "n_segments"] == len(result.segments)


@pytest.mark.parametrize("champion", ["B1_trailing_mean", "B3_tal_anchor"])
def test_the_export_survives_a_champion_without_segment_forecasts(champion, tables, cfg, monkeypatch):
    """If the champion ever changes to a portfolio-only model, the aggregates still build, validate and say 'no split'."""
    from jsonschema import Draft202012Validator, FormatChecker

    import halolens.export.aggregates as exporter
    from halolens.config import repo_root
    from halolens.contracts import AGGREGATES_SCHEMA
    from halolens.evaluate.backtest import all_models
    from halolens.forecast.asof import snapshot_for_year
    from halolens.market.registry import load_external

    def forced_pipeline(tables_, external_, cfg_, table=None):
        return {"champion": champion}

    def forced_forecast(tables_, external_, cfg_, year=None, table=None):
        year = cfg_["forecast_years"]["target_year"] if year is None else year
        return all_models()[champion](snapshot_for_year(tables_, external_, year, cfg_), cfg_)

    monkeypatch.setattr(exporter, "champion_pipeline", forced_pipeline)
    monkeypatch.setattr(exporter, "champion_forecast", forced_forecast)
    document = exporter.build_aggregates(tables, load_external(repo_root() / "data" / "public" / "sources.csv"), cfg)
    assert document["headline"]["model"] == champion
    assert document["headline"]["provinces"] == {"QC": {"net_pct": None, "contract_pct": None},
                                                 "ON": {"net_pct": None, "contract_pct": None}}
    assert list(Draft202012Validator(AGGREGATES_SCHEMA, format_checker=FormatChecker()).iter_errors(document)) == []
