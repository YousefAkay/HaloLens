"""Tests for the incentive engine (incentives.engine). Owner: FCT.

Hand-made leases with exact discount shares (net = contract x (1 - discount)): every segment has six units renewed each
January 1, so a cell always clears the minimum lease count. No CRM data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from halolens.contracts import LEASES_COLUMNS
from halolens.forecast.asof import make_snapshot
from halolens.incentives.engine import discount_share, forecast_discount, net_log_growth
from tests.test_baselines import empty_external, tables_from

CUTOFF = pd.Timestamp("2024-12-31")   # target year 2025
UNITS_PER_SEGMENT = 6                 # above incentives.min_leases_per_cell
YEARS = [2022, 2023, 2024]
CONTRACT_RENT = 1000.0
PRECISION = 1e-9


def make_segment_leases(prop_code: str, province: str, is_renewal: bool, discount_by_year: dict[int, float],
                        units: int = UNITS_PER_SEGMENT) -> pd.DataFrame:
    records = []
    for index in range(units):
        for seq, year in enumerate(YEARS, start=1):
            start = pd.Timestamp(f"{year}-01-01")
            discount = discount_by_year[year]
            records.append({
                "unit_id": f"{prop_code}{is_renewal}{index}", "prop_code": prop_code, "unit_code": f"{int(is_renewal)}{index:03d}",
                "building": prop_code, "province": province, "city": "Test", "beds": 1, "baths": 1.0, "sqft": 700,
                "floor": 1, "unit_type": "1_1", "lease_seq": seq, "is_renewal": is_renewal,
                "sign_date": start - pd.Timedelta(days=30), "lease_start": start,
                "lease_end": start + pd.DateOffset(years=1) - pd.Timedelta(days=1),
                "term_months_daycount": 12.0, "term_label": "Long Term", "rent_contract": CONTRACT_RENT,
                "rent_net_all_incentives": CONTRACT_RENT * (1 - discount), "has_concession": discount > 0})
    return pd.DataFrame(records)[LEASES_COLUMNS]


def discounts(first: float, second: float, third: float) -> dict[int, float]:
    return dict(zip(YEARS, (first, second, third)))


def run_engine(*leases: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    tables = tables_from(pd.concat(leases, ignore_index=True))
    return forecast_discount(make_snapshot(tables, empty_external(), CUTOFF), cfg)


def row(result: pd.DataFrame, prop_code: str, is_renewal: bool) -> pd.Series:
    selected = result[(result["prop_code"] == prop_code) & (result["is_renewal"] == is_renewal)]
    assert len(selected) == 1
    return selected.iloc[0]


# ---------------------------------------------------------------------------
# Arithmetic
# ---------------------------------------------------------------------------
def test_discount_share_is_one_minus_net_over_contract():
    leases = pd.DataFrame({"rent_contract": [1000.0, 1000.0, 0.0], "rent_net_all_incentives": [900.0, 1000.0, 0.0]})
    shares = discount_share(leases)
    assert shares.iloc[:2].tolist() == pytest.approx([0.1, 0.0])
    assert np.isnan(shares.iloc[2])


def test_five_percent_contract_growth_with_one_free_month_is_minus_3_75_percent_net():
    """Done-when check: 5% contract increase and one free month on a 12-month lease."""
    net_pct = 100 * np.expm1(net_log_growth(np.log(1.05), d0=0.0, d1=1 / 12))
    assert net_pct == pytest.approx(-3.75, abs=PRECISION)


def test_unchanged_discount_leaves_net_growth_equal_to_contract_growth():
    assert net_log_growth(0.04, d0=0.08, d1=0.08) == pytest.approx(0.04)


def test_growing_discount_lowers_net_growth_and_shrinking_discount_raises_it():
    assert net_log_growth(0.04, d0=0.02, d1=0.06) < 0.04
    assert net_log_growth(0.04, d0=0.06, d1=0.02) > 0.04


# ---------------------------------------------------------------------------
# forecast_discount
# ---------------------------------------------------------------------------
def test_d1_extends_the_straight_line_through_the_last_two_years(cfg):
    leases = make_segment_leases("aaa", "QC", False, discounts(0.0, 0.02, 0.04))
    row_ = row(run_engine(leases, cfg=cfg), "aaa", False)
    assert row_["d1"] == pytest.approx(0.06)       # 2023: 0.02, 2024: 0.04 -> 2025: 0.06
    assert row_["d1_source"] == "segment"


def test_d0_is_the_latest_years_discount(cfg):
    leases = make_segment_leases("aaa", "QC", False, discounts(0.0, 0.02, 0.04))
    assert row(run_engine(leases, cfg=cfg), "aaa", False)["d0"] == pytest.approx(0.04)


def test_renewals_and_turnovers_get_separate_d1_but_share_d0(cfg):
    """Turnovers carry the discount, renewals none; d0 pools both (equal counts -> average)."""
    turnover = make_segment_leases("aaa", "QC", False, discounts(0.10, 0.10, 0.10))
    renewal = make_segment_leases("aaa", "QC", True, discounts(0.0, 0.0, 0.0))
    result = run_engine(turnover, renewal, cfg=cfg)
    assert row(result, "aaa", False)["d1"] == pytest.approx(0.10)
    assert row(result, "aaa", True)["d1"] == pytest.approx(0.0)
    assert row(result, "aaa", False)["d0"] == pytest.approx(0.05)
    assert row(result, "aaa", True)["d0"] == pytest.approx(0.05)


def test_trend_is_clipped_between_zero_and_the_configured_maximum(cfg):
    rising = make_segment_leases("aaa", "QC", False, discounts(0.0, 0.20, 0.45))
    falling = make_segment_leases("bbb", "QC", False, discounts(0.0, 0.05, 0.01))
    result = run_engine(rising, falling, cfg=cfg)
    assert row(result, "aaa", False)["d1"] == pytest.approx(cfg["incentives"]["max_discount_share"])
    assert row(result, "bbb", False)["d1"] == 0.0


def test_one_usable_year_gives_a_flat_trend(cfg):
    one_year = {**cfg, "incentives": {**cfg["incentives"], "trend_window_years": 1}}
    leases = make_segment_leases("aaa", "QC", False, discounts(0.0, 0.02, 0.04))
    assert row(run_engine(leases, cfg=one_year), "aaa", False)["d1"] == pytest.approx(0.04)


def test_thin_segment_falls_back_to_its_province_pool(cfg):
    """bbb has two units (below the minimum): it uses the Ontario pool, which also contains bbb's own leases."""
    pool_discount = 0.08
    thin = make_segment_leases("bbb", "ON", False, discounts(0.0, 0.0, 0.0), units=2)
    thick = make_segment_leases("ccc", "ON", False, discounts(pool_discount, pool_discount, pool_discount))
    row_ = row(run_engine(thin, thick, cfg=cfg), "bbb", False)
    expected = pool_discount * UNITS_PER_SEGMENT / (UNITS_PER_SEGMENT + 2)
    assert row_["d1_source"] == "province_pool"
    assert row_["d1"] == pytest.approx(expected)
    assert row_["d0"] == pytest.approx(expected)


def test_output_has_the_contract_columns_and_one_row_per_weighted_segment(cfg):
    leases = make_segment_leases("aaa", "QC", False, discounts(0.0, 0.02, 0.04))
    result = run_engine(leases, cfg=cfg)
    assert {"prop_code", "beds", "is_renewal", "d0", "d1"} <= set(result.columns)
    assert len(result) == 1
    assert result["n_leases_d0"].iloc[0] == UNITS_PER_SEGMENT


def test_leases_starting_after_the_cutoff_cannot_change_the_forecast(cfg):
    """Adding a 2025 lease with a huge discount (not knowable at the end of 2024) changes nothing."""
    base = make_segment_leases("aaa", "QC", False, discounts(0.0, 0.02, 0.04))
    future = base.head(UNITS_PER_SEGMENT).copy()
    future["lease_start"] = pd.Timestamp("2025-01-01")
    future["sign_date"] = pd.Timestamp("2024-12-01")
    future["rent_net_all_incentives"] = CONTRACT_RENT * 0.2
    pd.testing.assert_frame_equal(run_engine(base, cfg=cfg), run_engine(base, future, cfg=cfg))


def test_no_discounts_gives_zero_shares(cfg):
    leases = make_segment_leases("aaa", "QC", False, discounts(0.0, 0.0, 0.0))
    row_ = row(run_engine(leases, cfg=cfg), "aaa", False)
    assert row_["d0"] == 0.0 and row_["d1"] == 0.0


def test_engine_runs_on_the_synthetic_snapshot(raw, cfg):
    """Smoke test on the committed synthetic fixtures (aggregates only)."""
    from halolens.io import canonicalize
    snapshot = make_snapshot(canonicalize(raw), empty_external(), pd.Timestamp("2024-12-31"))
    result = forecast_discount(snapshot, cfg)
    assert len(result) > 0
    assert result[["d0", "d1"]].notna().all().all()
    assert result["d1"].between(0, cfg["incentives"]["max_discount_share"]).all()


def test_province_with_too_few_leases_falls_back_to_the_portfolio_pool(cfg):
    """Ontario has only two units (below the minimum in every province-level cell), so bbb borrows the portfolio shares."""
    pooled_discount = 0.08
    thin = make_segment_leases("bbb", "ON", False, discounts(0.0, 0.0, 0.0), units=2)
    thick = make_segment_leases("aaa", "QC", False, discounts(pooled_discount, pooled_discount, pooled_discount))
    row_ = row(run_engine(thin, thick, cfg=cfg), "bbb", False)
    expected = pooled_discount * UNITS_PER_SEGMENT / (UNITS_PER_SEGMENT + 2)
    assert row_["d1_source"] == "portfolio_pool"
    assert row_["d1"] == pytest.approx(expected)
    assert row_["d0"] == pytest.approx(expected)
