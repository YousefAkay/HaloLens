"""Tests for same-unit lease matching (measure.pairs.build_pairs).

Written before the implementation.

Fixtures: hand-made leases (exact arithmetic) and the committed synthetic data. Never CRM data.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from halolens.contracts import DAYS_PER_YEAR, LEASES_COLUMNS, PAIRS_COLUMNS, PERCENT
from halolens.measure.pairs import (REASON_GAP_TOO_SHORT, REASON_NON_POSITIVE_RENT, REASON_SEPARATOR,
                                     REASON_UNIT_ID_MISMATCH, build_pairs, exclusion_summary, gap_sensitivity,
                                     key_comparison)

BASE_RENT = 1000.0


def make_leases(rows: list[dict]) -> pd.DataFrame:
    """Hand-made leases in the canonical LEASES schema. Each row needs unit_id, lease_start and rents."""
    defaults = {
        "prop_code": "aaa", "unit_code": "0101", "building": "Test Building", "province": "QC",
        "city": "Laval", "beds": 1, "baths": 1.0, "sqft": 700, "floor": 1, "unit_type": "1_1",
        "is_renewal": False, "term_label": "Long Term", "term_months_daycount": 12.0,
    }
    records = []
    for seq, row in enumerate(rows, start=1):
        record = {**defaults, **row}
        start = pd.Timestamp(record["lease_start"])
        record["lease_start"] = start
        record.setdefault("sign_date", start - pd.Timedelta(days=30))
        record.setdefault("lease_end", start + pd.DateOffset(years=1) - pd.Timedelta(days=1))
        record.setdefault("lease_seq", seq)
        record.setdefault("rent_net_all_incentives", record["rent_contract"])
        record["has_concession"] = record["rent_net_all_incentives"] < record["rent_contract"]
        records.append(record)
    df = pd.DataFrame(records)
    for column in ["sign_date", "lease_start", "lease_end"]:
        df[column] = pd.to_datetime(df[column])
    return df[LEASES_COLUMNS]


def one_unit(starts: list[str], rents: list[float], **extra) -> pd.DataFrame:
    return make_leases([{"unit_id": "u1", "lease_start": s, "rent_contract": r, **extra}
                        for s, r in zip(starts, rents)])


# ---------------------------------------------------------------------------
# Key safety on the source data
# ---------------------------------------------------------------------------
def test_unsafe_site_key_merges_distinct_units(raw):
    """sSite + sUnitCode maps one key to several hUnit values: matching on it would mix apartments."""
    leases = raw["leases"]
    units_per_unsafe_key = leases.groupby(["sSite", "sUnitCode"])["hUnit"].nunique()
    assert (units_per_unsafe_key > 1).any()


def test_safe_key_identifies_exactly_one_unit(raw):
    """sPropCode + sUnitCode and hUnit are one-to-one, so either can serve as the matching key."""
    leases = raw["leases"]
    assert (leases.groupby(["sPropCode", "sUnitCode"])["hUnit"].nunique() == 1).all()
    assert (leases.groupby("hUnit")[["sPropCode", "sUnitCode"]].nunique() == 1).all().all()


def test_key_comparison_counts_cross_unit_pairs_only_for_unsafe_key(raw):
    """The section 04 demo: the safe key never pairs two apartments, the unsafe key does."""
    comparison = key_comparison(raw["leases"]).set_index("key")
    safe, unsafe = comparison.iloc[0], comparison.iloc[1]
    assert safe["n_cross_unit_pairs"] == 0 and safe["n_keys_with_several_units"] == 0
    assert safe["n_keys"] == safe["n_units"]
    assert unsafe["n_cross_unit_pairs"] > 0 and unsafe["n_keys"] < unsafe["n_units"]


# ---------------------------------------------------------------------------
# Growth arithmetic (hand-made fixtures)
# ---------------------------------------------------------------------------
def test_constant_price_gives_zero_growth(cfg):
    pairs = build_pairs(one_unit(["2022-01-01", "2023-01-01", "2024-01-01"], [BASE_RENT] * 3), cfg)
    eligible = pairs[pairs["eligible"]]
    assert len(eligible) == 2
    assert np.allclose(eligible["loggrowth_contract"], 0.0)
    assert np.allclose(eligible["loggrowth_net"], 0.0)


def test_doubling_over_twelve_months_is_about_100_pct(cfg):
    pairs = build_pairs(one_unit(["2023-01-01", "2024-01-01"], [BASE_RENT, 2 * BASE_RENT]), cfg)
    pair = pairs.iloc[0]
    assert pair["eligible"]
    expected_gap = (pd.Timestamp("2024-01-01") - pd.Timestamp("2023-01-01")).days / DAYS_PER_YEAR
    assert pair["gap_years"] == pytest.approx(expected_gap)
    assert pair["loggrowth_contract"] == pytest.approx(math.log(2) / expected_gap)
    annual_pct = PERCENT * (math.exp(pair["loggrowth_contract"]) - 1)
    assert annual_pct == pytest.approx(PERCENT, rel=0.01)  # 365/365.25 day-count leaves a ~0.1% gap


def test_growth_is_annualized_over_the_gap(cfg):
    """A 10% rise over two years is ~4.9%/year, not 10%."""
    pairs = build_pairs(one_unit(["2022-01-01", "2024-01-01"], [BASE_RENT, 1.1 * BASE_RENT]), cfg)
    pair = pairs.iloc[0]
    assert pair["loggrowth_contract"] == pytest.approx(math.log(1.1) / pair["gap_years"])


def test_net_and_contract_growth_use_their_own_rents(cfg):
    leases = make_leases([
        {"unit_id": "u1", "lease_start": "2023-01-01", "rent_contract": BASE_RENT},
        {"unit_id": "u1", "lease_start": "2024-01-01", "rent_contract": 1.05 * BASE_RENT,
         "rent_net_all_incentives": 0.95 * BASE_RENT},
    ])
    pair = build_pairs(leases, cfg).iloc[0]
    assert pair["loggrowth_contract"] == pytest.approx(math.log(1.05) / pair["gap_years"])
    assert pair["loggrowth_net"] == pytest.approx(math.log(0.95) / pair["gap_years"])
    assert pair["rent_net_prev"] == BASE_RENT and pair["rent_net"] == 0.95 * BASE_RENT


# ---------------------------------------------------------------------------
# Matching key: never mix apartments that share a unit code
# ---------------------------------------------------------------------------
def test_same_unit_code_in_two_properties_is_never_paired(cfg):
    """Two apartments with unit code 0101 on one site (different prop_code) stay separate."""
    leases = make_leases([
        {"unit_id": "u1", "prop_code": "aaa", "lease_start": "2023-01-01", "rent_contract": BASE_RENT},
        {"unit_id": "u2", "prop_code": "bbb", "lease_start": "2023-06-01", "rent_contract": 2 * BASE_RENT},
        {"unit_id": "u1", "prop_code": "aaa", "lease_start": "2024-01-01", "rent_contract": BASE_RENT},
        {"unit_id": "u2", "prop_code": "bbb", "lease_start": "2024-06-01", "rent_contract": 2 * BASE_RENT},
    ])
    pairs = build_pairs(leases, cfg)
    assert len(pairs) == 2
    assert set(pairs["unit_id"]) == {"u1", "u2"}
    assert np.allclose(pairs["loggrowth_contract"], 0.0)


def test_pairs_are_consecutive_by_lease_start_regardless_of_row_order(cfg):
    leases = one_unit(["2024-01-01", "2022-01-01", "2023-01-01"], [1.2 * BASE_RENT, BASE_RENT, 1.1 * BASE_RENT])
    pairs = build_pairs(leases, cfg).sort_values("lease_start")
    assert list(pairs["prev_lease_start"]) == [pd.Timestamp("2022-01-01"), pd.Timestamp("2023-01-01")]
    assert (pairs["loggrowth_contract"] > 0).all()


# ---------------------------------------------------------------------------
# Eligibility and exclusion audit
# ---------------------------------------------------------------------------
def test_gap_outside_config_bounds_is_excluded_with_reason(cfg):
    bounds = cfg["pairs"]
    too_short = pd.Timestamp("2023-01-01") + pd.Timedelta(days=bounds["min_gap_years"] * DAYS_PER_YEAR / 2)
    too_long = too_short + pd.Timedelta(days=(bounds["max_gap_years"] + 1) * DAYS_PER_YEAR)
    pairs = build_pairs(one_unit(["2023-01-01", too_short.strftime("%Y-%m-%d"), too_long.strftime("%Y-%m-%d")],
                                 [BASE_RENT] * 3), cfg)
    assert len(pairs) == 2
    assert not pairs["eligible"].any()
    assert (pairs["exclusion_reason"].str.len() > 0).all()


def test_non_positive_rent_is_excluded_with_reason(cfg):
    pairs = build_pairs(one_unit(["2023-01-01", "2024-01-01"], [BASE_RENT, 0.0]), cfg)
    pair = pairs.iloc[0]
    assert not pair["eligible"]
    assert len(pair["exclusion_reason"]) > 0


def test_pair_year_is_year_of_later_lease_start(cfg):
    pairs = build_pairs(one_unit(["2023-03-01", "2024-02-01"], [BASE_RENT, BASE_RENT]), cfg)
    assert pairs.iloc[0]["year"] == 2024


# ---------------------------------------------------------------------------
# Contract and audit invariants on the synthetic data
# ---------------------------------------------------------------------------
def test_output_matches_pairs_contract(tables, cfg):
    pairs = build_pairs(tables.leases, cfg)
    assert list(pairs.columns) == PAIRS_COLUMNS
    assert pairs["eligible"].dtype == bool


def test_every_consecutive_pair_is_kept_and_audited(tables, cfg):
    """One row per consecutive pair (eligible or not); every exclusion carries a reason."""
    leases = tables.leases
    pairs = build_pairs(leases, cfg)
    assert len(pairs) == len(leases) - leases["unit_id"].nunique()
    excluded = pairs[~pairs["eligible"]]
    assert (excluded["exclusion_reason"].str.len() > 0).all()
    assert (pairs.loc[pairs["eligible"], "exclusion_reason"] == "").all()


def test_eligible_pairs_respect_gap_bounds(tables, cfg):
    bounds = cfg["pairs"]
    eligible = build_pairs(tables.leases, cfg).query("eligible")
    assert len(eligible) > 0
    assert (eligible["gap_years"] > bounds["min_gap_years"]).all()
    assert (eligible["gap_years"] < bounds["max_gap_years"]).all()


def test_input_is_not_modified(tables, cfg):
    before = tables.leases.copy()
    build_pairs(tables.leases, cfg)
    pd.testing.assert_frame_equal(tables.leases, before)


# ---------------------------------------------------------------------------
# Audit details and gap sensitivity
# ---------------------------------------------------------------------------
def test_pair_failing_two_rules_lists_both_reasons(cfg):
    short = pd.Timestamp("2023-01-01") + pd.Timedelta(days=cfg["pairs"]["min_gap_years"] * DAYS_PER_YEAR / 2)
    pairs = build_pairs(one_unit(["2023-01-01", short.strftime("%Y-%m-%d")], [BASE_RENT, 0.0]), cfg)
    reasons = set(pairs.iloc[0]["exclusion_reason"].split(REASON_SEPARATOR))
    assert reasons == {REASON_GAP_TOO_SHORT, REASON_NON_POSITIVE_RENT}


def test_unit_id_disagreeing_with_safe_key_is_excluded(cfg):
    """Same prop_code + unit_code but different hUnit: the cross-check rejects the pair instead of guessing."""
    leases = make_leases([
        {"unit_id": "u1", "lease_start": "2023-01-01", "rent_contract": BASE_RENT},
        {"unit_id": "u9", "lease_start": "2024-01-01", "rent_contract": BASE_RENT},
    ])
    pair = build_pairs(leases, cfg).iloc[0]
    assert not pair["eligible"]
    assert pair["exclusion_reason"] == REASON_UNIT_ID_MISMATCH


def test_exclusion_summary_counts_add_up(tables, cfg):
    pairs = build_pairs(tables.leases, cfg)
    summary = exclusion_summary(pairs).set_index("exclusion_reason")["n_pairs"]
    assert summary["(eligible)"] == pairs["eligible"].sum()
    assert summary.drop("(eligible)").sum() >= (~pairs["eligible"]).sum()


def test_gap_sensitivity_admits_six_month_leases(cfg):
    """A 182-day gap (just under 0.5 years) is excluded at base bounds and kept by the sensitivity bound."""
    pairs = build_pairs(one_unit(["2023-01-01", "2023-07-02", "2024-07-01"], [BASE_RENT] * 3), cfg)
    assert pairs.iloc[0]["gap_years"] < cfg["pairs"]["min_gap_years"]
    table = gap_sensitivity(pairs, cfg).set_index("scenario")
    assert table.loc["base", "n_eligible"] == pairs["eligible"].sum() == 1
    assert table.loc["include_six_month", "n_eligible"] == 2
    assert table.loc["include_six_month", "median_net_pct"] == pytest.approx(0.0)


def test_gap_sensitivity_keeps_non_gap_exclusions(cfg):
    pairs = build_pairs(one_unit(["2023-01-01", "2023-07-02"], [BASE_RENT, 0.0]), cfg)
    table = gap_sensitivity(pairs, cfg).set_index("scenario")
    assert (table["n_eligible"] == 0).all()
