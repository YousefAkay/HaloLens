"""Tests for the headline helpers and baselines B0-B2 (forecast.baselines). Owner: FCT.

Hand-made leases with exact yearly growth (2020 is the high year, 2022 the low one, so the training winsor bounds
span every later year and clipping does not bite): four units (two QC, two ON) renewed every January 1 from 2019 to 2025,
all with the same growth in a given year, so each baseline has a known answer. No CRM data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from leaselens.contracts import (ASKING_COLUMNS, CONCESSIONS_COLUMNS, EXTERNAL_COLUMNS, LEASES_COLUMNS, PERCENT,
                                 UNITS_COLUMNS, CanonicalTables)
from leaselens.forecast.asof import make_snapshot
from leaselens.forecast.baselines import (BASELINES, frozen_weights, headline_summary, last_year, market_anchor,
                                          to_pct, trailing_mean, training_pairs, winsor_bounds)

START_RENT = 1000.0
FIRST_YEAR = 2019
YEARLY_GROWTH = {2020: 0.05, 2021: 0.03, 2022: 0.02, 2023: 0.03, 2024: 0.04, 2025: 0.05}
MARKET_GROWTH_PCT = {2022: 1.0, 2023: 2.0, 2024: 3.0}   # released before the end of each year
UNITS = [("aaa", "QC", "0101"), ("aaa", "QC", "0102"), ("bbb", "ON", "0201"), ("bbb", "ON", "0202")]
CUTOFF_2025 = pd.Timestamp("2024-12-31")
ABS_TOLERANCE_PP = 0.05   # leap years make the gap 0.9993 or 1.0021 years, not exactly 1


def annual_leases(growth: dict[int, float] = YEARLY_GROWTH, units=UNITS) -> pd.DataFrame:
    records = []
    for prop_code, province, unit_code in units:
        rent = START_RENT
        for seq, year in enumerate(range(FIRST_YEAR, max(growth) + 1), start=1):
            rent *= 1 + growth.get(year, 0.0)
            start = pd.Timestamp(f"{year}-01-01")
            records.append({
                "unit_id": f"{prop_code}{unit_code}", "prop_code": prop_code, "unit_code": unit_code,
                "building": prop_code, "province": province, "city": "Test", "beds": 1, "baths": 1.0, "sqft": 700,
                "floor": 1, "unit_type": "1_1", "lease_seq": seq, "is_renewal": True,
                "sign_date": start - pd.Timedelta(days=30), "lease_start": start,
                "lease_end": start + pd.DateOffset(years=1) - pd.Timedelta(days=1),
                "term_months_daycount": 12.0, "term_label": "Long Term",
                "rent_contract": rent, "rent_net_all_incentives": rent, "has_concession": False})
    return pd.DataFrame(records)[LEASES_COLUMNS]


def tables_from(leases: pd.DataFrame) -> CanonicalTables:
    return CanonicalTables(leases=leases, concessions=pd.DataFrame(columns=CONCESSIONS_COLUMNS),
                           asking=pd.DataFrame(columns=ASKING_COLUMNS).astype({"month": "period[M]"}),
                           units=pd.DataFrame(columns=UNITS_COLUMNS))


def market_rows(include_post_cutoff: bool = True) -> pd.DataFrame:
    rows = []
    values = dict(MARKET_GROWTH_PCT)
    if include_post_cutoff:
        values[2025] = 9.9
    for year, value in values.items():
        for geography in ("QC", "ON"):
            rows.append({"series_id": f"{geography}_{year}", "publisher": "test", "geography": geography,
                         "metric": "rent_cpi", "unit": "pct", "value": value,
                         "ref_period_start": pd.Timestamp(f"{year}-01-01"),
                         "ref_period_end": pd.Timestamp(f"{year}-10-31"),
                         "release_date": pd.Timestamp(f"{year}-11-30")})
    return pd.DataFrame(rows).reindex(columns=EXTERNAL_COLUMNS)


def empty_external() -> pd.DataFrame:
    return pd.DataFrame(columns=EXTERNAL_COLUMNS).astype({"release_date": "datetime64[ns]"})


@pytest.fixture(scope="module")
def tables() -> CanonicalTables:
    return tables_from(annual_leases())


@pytest.fixture(scope="module")
def snapshot(tables):
    return make_snapshot(tables, market_rows(), CUTOFF_2025)


def log_growth(year: int) -> float:
    return float(np.log1p(YEARLY_GROWTH[year]))


# ---------------------------------------------------------------------------
# Headline helpers
# ---------------------------------------------------------------------------
def test_to_pct_inverts_the_log_growth():
    assert to_pct(np.log(1.05)) == pytest.approx(5.0)
    assert to_pct(0.0) == 0.0


def test_weights_are_shares_of_window_pairs_and_sum_to_one(snapshot, cfg):
    weights = frozen_weights(training_pairs(snapshot, cfg), CUTOFF_2025, cfg)
    assert weights["weight"].sum() == pytest.approx(1.0)
    assert set(weights["prop_code"]) == {"aaa", "bbb"}
    assert weights["weight"].tolist() == pytest.approx([0.5, 0.5])


def test_weights_use_only_the_window_before_the_cutoff(snapshot, cfg):
    """With a one-year window only 2024 pairs count: 4 pairs."""
    short = {**cfg, "headline": {**cfg["headline"], "weight_window_years": 1}}
    weights = frozen_weights(training_pairs(snapshot, short), CUTOFF_2025, short)
    assert weights["n_pairs_window"].sum() == len(UNITS)


def test_headline_uses_frozen_weights_not_the_target_year_mix(cfg):
    """Segment A grows 10%, B grows 0%. Frozen weights are 75/25, but the target year has one A pair and three B pairs."""
    keys = list(cfg["headline"]["segment_keys"])
    weights = pd.DataFrame([["aaa", 1, True, 3, 0.75], ["bbb", 1, True, 1, 0.25]],
                           columns=keys + ["n_pairs_window", "weight"])
    log_ten = float(np.log(1.1))
    rows = [("aaa", log_ten)] + [("bbb", 0.0)] * 3
    pairs = pd.DataFrame({"unit_id": [f"u{i}" for i in range(4)], "prop_code": [r[0] for r in rows], "beds": 1,
                          "is_renewal": True, "loggrowth_net": [r[1] for r in rows],
                          "loggrowth_contract": [r[1] for r in rows]})
    summary = headline_summary(pairs, weights, {}, cfg)
    assert summary["log_net"] == pytest.approx(0.75 * log_ten)
    assert summary["coverage"] == pytest.approx(1.0)


def test_headline_renormalizes_and_reports_coverage_when_a_segment_has_no_pairs(cfg):
    keys = list(cfg["headline"]["segment_keys"])
    weights = pd.DataFrame([["aaa", 1, True, 3, 0.75], ["bbb", 1, True, 1, 0.25]],
                           columns=keys + ["n_pairs_window", "weight"])
    pairs = pd.DataFrame({"unit_id": ["u0"], "prop_code": ["bbb"], "beds": 1, "is_renewal": True,
                          "loggrowth_net": [0.1], "loggrowth_contract": [0.1]})
    summary = headline_summary(pairs, weights, {}, cfg)
    assert summary["coverage"] == pytest.approx(0.25)
    assert summary["log_net"] == pytest.approx(0.1)


def test_headline_is_none_without_pairs(cfg):
    assert headline_summary(pd.DataFrame(), pd.DataFrame(), {}, cfg) is None


def test_winsor_bounds_are_the_training_quantiles(snapshot, cfg):
    pairs = training_pairs(snapshot, cfg)
    bounds = winsor_bounds(pairs, cfg)
    low, high = cfg["winsorize"]["lower_quantile"], cfg["winsorize"]["upper_quantile"]
    assert bounds["loggrowth_net"] == pytest.approx((pairs["loggrowth_net"].quantile(low),
                                                     pairs["loggrowth_net"].quantile(high)))


def test_winsorizing_clips_an_outlier_pair(cfg):
    keys = list(cfg["headline"]["segment_keys"])
    weights = pd.DataFrame([["aaa", 1, True, 5, 1.0]], columns=keys + ["n_pairs_window", "weight"])
    pairs = pd.DataFrame({"unit_id": list("abcde"), "prop_code": "aaa", "beds": 1, "is_renewal": True,
                          "loggrowth_net": [0.0, 0.0, 0.0, 0.0, 5.0], "loggrowth_contract": [0.0] * 5})
    clipped = headline_summary(pairs, weights, {"loggrowth_net": (0.0, 0.1), "loggrowth_contract": (0.0, 0.1)}, cfg)
    assert clipped["log_net"] == pytest.approx(0.1 / 5)


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------
def test_b0_repeats_last_years_growth(snapshot, cfg):
    result = last_year(snapshot, cfg)
    assert result.target_year == 2025
    assert result.model_name == "B0_last_year"
    assert result.headline_net_pct == pytest.approx(YEARLY_GROWTH[2024] * PERCENT, abs=ABS_TOLERANCE_PP)
    assert result.headline_contract_pct == pytest.approx(result.headline_net_pct)


def test_b1_averages_the_trailing_window_on_the_log_scale(snapshot, cfg):
    result = trailing_mean(snapshot, cfg)
    window = [2022, 2023, 2024]
    expected = to_pct(np.mean([log_growth(year) for year in window]))
    assert result.components["years_used"] == window
    assert result.headline_net_pct == pytest.approx(expected, abs=ABS_TOLERANCE_PP)


def test_b2_adds_the_historical_gap_to_the_latest_market_growth(snapshot, cfg):
    result = market_anchor(snapshot, cfg)
    market_log = {year: np.log1p(value / PERCENT) for year, value in MARKET_GROWTH_PCT.items()}
    gap = np.mean([log_growth(year) - market_log[year] for year in (2022, 2023, 2024)])
    assert result.components["market_year"] == 2024
    assert result.headline_net_pct == pytest.approx(to_pct(market_log[2024] + gap), abs=ABS_TOLERANCE_PP)


def test_b2_ignores_market_rows_released_after_the_cutoff(tables, cfg):
    with_future = market_anchor(make_snapshot(tables, market_rows(include_post_cutoff=True), CUTOFF_2025), cfg)
    without = market_anchor(make_snapshot(tables, market_rows(include_post_cutoff=False), CUTOFF_2025), cfg)
    assert with_future.headline_net_pct == without.headline_net_pct


def test_b2_needs_released_market_data(tables, cfg):
    with pytest.raises(ValueError, match="market"):
        market_anchor(make_snapshot(tables, empty_external(), CUTOFF_2025), cfg)


@pytest.mark.parametrize("name", list(BASELINES))
def test_baselines_ignore_leases_that_start_after_the_cutoff(name, tables, cfg):
    """Dropping every 2025 lease must not change a baseline forecast made at the end of 2024."""
    leases = tables.leases
    truncated = tables_from(leases[leases["lease_start"] <= CUTOFF_2025])
    full = BASELINES[name](make_snapshot(tables, market_rows(), CUTOFF_2025), cfg)
    early = BASELINES[name](make_snapshot(truncated, market_rows(), CUTOFF_2025), cfg)
    assert full.headline_net_pct == early.headline_net_pct
    assert full.median_contract_pct == early.median_contract_pct


@pytest.mark.parametrize("name", list(BASELINES))
def test_baseline_results_follow_the_forecast_result_contract(name, snapshot, cfg):
    result = BASELINES[name](snapshot, cfg)
    assert result.cutoff == CUTOFF_2025
    assert result.assumptions
    assert isinstance(result.segments, pd.DataFrame) and not result.segments.empty


def test_baselines_run_on_the_synthetic_snapshot(raw, cfg):
    """Smoke test on the committed synthetic fixtures (counts only)."""
    from leaselens.io import canonicalize
    synthetic = canonicalize(raw)
    snap = make_snapshot(synthetic, empty_external(), pd.Timestamp("2024-12-31"))
    for name in ("B0_last_year", "B1_trailing_mean"):
        result = BASELINES[name](snap, cfg)
        assert np.isfinite(result.headline_net_pct)
