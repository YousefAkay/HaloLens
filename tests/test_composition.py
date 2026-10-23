"""Tests for the composition / rent bridge (measure.composition).

Fixtures: hand-made leases (exact arithmetic) and the committed synthetic data. Never CRM data.
"""

from __future__ import annotations

import copy
import math

import numpy as np
import pandas as pd
import pytest

from halolens.contracts import LEASES_COLUMNS, PERCENT
from halolens.measure.composition import (BRIDGE_COLUMNS, NOTE_NO_WEIGHTS, mix_by_year, rent_bridge)
from halolens.measure.pairs import build_pairs

CHEAP_RENT = 1000.0
DEAR_RENT = 3000.0
FIRST_YEAR = 2016
LAST_YEAR = 2021
MIX_SHIFT_YEAR = 2020


def lease(unit: str, year: int, rent: float, net: float | None = None, renewal: bool = False) -> dict:
    """One canonical lease starting on March 1 of `year` (unit_code = unit_id, so the safe key is unique)."""
    start = pd.Timestamp(f"{year}-03-01")
    net = rent if net is None else net
    return {
        "unit_id": unit, "prop_code": "aaa", "unit_code": unit, "building": "Test Building", "province": "QC",
        "city": "Laval", "beds": 1, "baths": 1.0, "sqft": 700, "floor": 1, "unit_type": "1_1",
        "lease_seq": year - FIRST_YEAR + 1, "is_renewal": renewal, "sign_date": start - pd.Timedelta(days=30),
        "lease_start": start, "lease_end": start + pd.DateOffset(years=1) - pd.Timedelta(days=1),
        "term_months_daycount": 12.0, "term_label": "Long Term", "rent_contract": rent,
        "rent_net_all_incentives": net, "has_concession": net < rent,
    }


def leases_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)[LEASES_COLUMNS]


@pytest.fixture
def small_cfg(cfg) -> dict:
    """Config with the bridge starting right after the first year of hand-made leases."""
    adjusted = copy.deepcopy(cfg)
    adjusted["composition"]["naive_years_start"] = FIRST_YEAR + 1
    return adjusted


def bridge_of(leases: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    return rent_bridge(leases, build_pairs(leases, cfg), cfg).set_index("year")


def test_mix_shift_shows_in_naive_but_not_in_same_unit(small_cfg):
    """Constant rents per unit: an extra dear unit leased in one year moves the naive median, not same-unit growth."""
    rows = [lease(unit, year, rent) for year in range(FIRST_YEAR, LAST_YEAR + 1)
            for unit, rent in (("A", CHEAP_RENT), ("B", DEAR_RENT))]
    rows.append(lease("C", MIX_SHIFT_YEAR, DEAR_RENT))
    bridge = bridge_of(leases_frame(rows), small_cfg)
    year = bridge.loc[MIX_SHIFT_YEAR]
    expected_naive = math.log(DEAR_RENT / ((CHEAP_RENT + DEAR_RENT) / 2))
    assert year["naive_log_contract"] == pytest.approx(expected_naive)
    assert year["same_unit_log_contract"] == pytest.approx(0.0)
    assert year["composition_log"] == pytest.approx(expected_naive)


def test_incentive_effect_is_net_minus_contract(small_cfg):
    """Contract rent constant, net rent cut by a concession in the last year: the bridge isolates it.

    Unit B alternates between two rents (same rent contract and net) so the training bounds are wide; winsorizing at
    the training min/max then clips nothing. Both units share one segment, so the segment mean halves A's cut.
    """
    no_clip = copy.deepcopy(small_cfg)
    no_clip["winsorize"].update(lower_quantile=0.0, upper_quantile=1.0)
    discounted = CHEAP_RENT * (1 - 1 / 12)  # one free month spread over a 12-month lease
    rows = [lease("A", year, CHEAP_RENT, discounted if year == LAST_YEAR else None)
            for year in range(FIRST_YEAR, LAST_YEAR + 1)]
    rows += [lease("B", year, DEAR_RENT if year % 2 else CHEAP_RENT) for year in range(FIRST_YEAR, LAST_YEAR + 1)]
    year = bridge_of(leases_frame(rows), no_clip).loc[LAST_YEAR]
    expected_contract = math.log(DEAR_RENT / CHEAP_RENT) / 2
    assert year["same_unit_log_contract"] == pytest.approx(expected_contract, rel=1e-3)
    assert year["incentive_log"] == pytest.approx(math.log(discounted / CHEAP_RENT) / 2, rel=1e-3)


def test_parts_add_exactly_on_log_scale(tables, cfg):
    bridge = rent_bridge(tables.leases, build_pairs(tables.leases, cfg), cfg)
    complete = bridge.dropna(subset=["naive_log_contract", "same_unit_log_contract"])
    assert not complete.empty
    np.testing.assert_allclose(complete["same_unit_log_contract"] + complete["composition_log"],
                               complete["naive_log_contract"])
    np.testing.assert_allclose(complete["same_unit_log_contract"] + complete["incentive_log"],
                               complete["same_unit_log_net"])
    np.testing.assert_allclose(complete["composition_pp"], PERCENT * complete["composition_log"])


def test_output_columns_and_year_range(tables, cfg):
    bridge = rent_bridge(tables.leases, build_pairs(tables.leases, cfg), cfg)
    assert list(bridge.columns) == BRIDGE_COLUMNS
    assert bridge["year"].min() == cfg["composition"]["naive_years_start"]
    assert bridge["year"].max() == tables.leases["lease_start"].dt.year.max()
    assert bridge["year"].is_unique


def test_year_without_weight_window_keeps_nan_and_note(cfg):
    """With no eligible pairs before the cutoff the same-unit figure is not invented."""
    adjusted = copy.deepcopy(cfg)
    adjusted["composition"]["naive_years_start"] = FIRST_YEAR + 1
    rows = [lease("A", year, CHEAP_RENT) for year in range(FIRST_YEAR, FIRST_YEAR + 2)]
    year = bridge_of(leases_frame(rows), adjusted).loc[FIRST_YEAR + 1]
    assert math.isnan(year["same_unit_log_contract"])
    assert year["note"] == NOTE_NO_WEIGHTS
    assert year["naive_log_contract"] == pytest.approx(0.0)


def test_bridge_does_not_modify_inputs(tables, cfg):
    leases_before = tables.leases.copy()
    pairs = build_pairs(tables.leases, cfg)
    pairs_before = pairs.copy()
    rent_bridge(tables.leases, pairs, cfg)
    pd.testing.assert_frame_equal(tables.leases, leases_before)
    pd.testing.assert_frame_equal(pairs, pairs_before)


def test_mix_shares_sum_to_one(tables, cfg):
    shares = mix_by_year(tables.leases, "is_renewal", cfg)
    assert shares.index.min() >= cfg["composition"]["naive_years_start"]
    np.testing.assert_allclose(shares.sum(axis=1), 1.0)
