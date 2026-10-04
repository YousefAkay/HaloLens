"""Tests for the asking-rent turnover signal (market.asking). Owner: MSR.

Fixtures: hand-made snapshots (exact arithmetic) and the committed synthetic data. Never CRM data.
"""

from __future__ import annotations

import copy
import math

import numpy as np
import pandas as pd
import pytest

from leaselens.config import cutoff_for
from leaselens.contracts import ASKING_COLUMNS, DAYS_PER_YEAR, LEASES_COLUMNS, Snapshot
from leaselens.forecast.asof import make_snapshot
from leaselens.forecast.baselines import frozen_weights, training_pairs
from leaselens.market.asking import (SIGNAL_COLUMNS, SOURCE_PROVINCE, SOURCE_SEGMENT, listing_growth,
                                     matched_spreads, turnover_signal)

CUTOFF = pd.Timestamp("2024-12-31")
PRIOR_RENT = 1000.0
ASKING_RENT = 1100.0
SIGNED_RENT = 1050.0
SYNTHETIC_FOLD_YEAR = 2025      # cutoff 2024-12-31: synthetic asking and leases exist on both sides
FUTURE_RENT_MULTIPLIER = 10.0   # fake post-cutoff asking rents, so any leak moves the signal visibly


@pytest.fixture()
def loose_cfg(cfg) -> dict:
    """Synthetic config with pooling thresholds at one and a one-month signal window (only the cutoff month's
    listings), so a single hand-made unit is enough."""
    loose = copy.deepcopy(cfg)
    loose["asking"]["signal_window_months"] = 1
    loose["asking"]["min_listings_per_segment"] = 1
    loose["asking"]["min_spread_leases"] = 1
    return loose


def lease(prop_code: str, unit_code: str, start: str, rent: float, is_renewal: bool = False,
          sign: str | None = None, beds: int = 1) -> dict:
    start_ts = pd.Timestamp(start)
    return {
        "unit_id": f"{prop_code}-{unit_code}", "prop_code": prop_code, "unit_code": unit_code,
        "building": prop_code, "province": "QC", "city": "Laval", "beds": beds, "baths": 1.0, "sqft": 700,
        "floor": 1, "unit_type": "1_1", "lease_seq": 1, "is_renewal": is_renewal,
        "sign_date": pd.Timestamp(sign) if sign else start_ts - pd.Timedelta(days=30), "lease_start": start_ts,
        "lease_end": start_ts + pd.DateOffset(years=1), "term_months_daycount": 12.0, "term_label": "Long Term",
        "rent_contract": rent, "rent_net_all_incentives": rent, "has_concession": False,
    }


def asking_row(prop_code: str, unit_code: str, month: str, rent: float, beds: int = 1) -> dict:
    return {"unit_id": f"{prop_code}-{unit_code}", "prop_code": prop_code, "unit_code": unit_code,
            "building": prop_code, "province": "QC", "beds": beds, "sqft": 700,
            "month": pd.Period(month, freq="M"), "asking_rent": rent}


def snapshot_of(leases: list[dict], asking: list[dict]) -> Snapshot:
    return Snapshot(cutoff=CUTOFF, leases=pd.DataFrame(leases, columns=LEASES_COLUMNS),
                    concessions=pd.DataFrame(), asking=pd.DataFrame(asking, columns=ASKING_COLUMNS),
                    units=None, external=pd.DataFrame())


@pytest.fixture()
def hand_snapshot() -> Snapshot:
    """Unit 0101: listed in 2024-12 over a 2024-01 lease. Unit 0102: turnover signed 2024-06 from a 2024-05 asking."""
    leases = [
        lease("aaa", "0101", "2023-01-01", PRIOR_RENT * 0.97),
        lease("aaa", "0101", "2024-01-01", PRIOR_RENT, is_renewal=True),
        lease("aaa", "0102", "2023-07-01", PRIOR_RENT),
        lease("aaa", "0102", "2024-07-01", SIGNED_RENT, sign="2024-06-15"),
    ]
    asking = [asking_row("aaa", "0102", "2024-05", PRIOR_RENT), asking_row("aaa", "0101", "2024-12", ASKING_RENT)]
    return snapshot_of(leases, asking)


def test_spread_is_signed_over_latest_asking_before_signing(hand_snapshot, loose_cfg):
    spreads = matched_spreads(hand_snapshot, loose_cfg)
    assert len(spreads) == 1
    assert spreads["spread_log"].iloc[0] == pytest.approx(math.log(SIGNED_RENT / PRIOR_RENT))


def test_asking_long_before_signing_is_not_matched(hand_snapshot, loose_cfg):
    lookback = loose_cfg["asking"]["match_lookback_months"]
    stale = pd.Period("2024-06", freq="M") - (lookback + 1)
    asking = hand_snapshot.asking.assign(month=hand_snapshot.asking["month"].where(
        hand_snapshot.asking["unit_code"] != "0102", stale))
    snapshot = Snapshot(CUTOFF, hand_snapshot.leases, hand_snapshot.concessions, asking, None, hand_snapshot.external)
    assert matched_spreads(snapshot, loose_cfg).empty


def test_listing_growth_exact_annualized_log(hand_snapshot, loose_cfg):
    growth = listing_growth(hand_snapshot, loose_cfg)
    expected_gap = (pd.Timestamp("2024-12-01") - pd.Timestamp("2024-01-01")).days / DAYS_PER_YEAR
    assert len(growth) == 1
    assert growth["gap_years"].iloc[0] == pytest.approx(expected_gap)
    assert growth["asking_loggrowth"].iloc[0] == pytest.approx(math.log(ASKING_RENT / PRIOR_RENT) / expected_gap)


def test_lease_starting_in_asking_month_is_not_its_own_base(loose_cfg):
    leases = [lease("aaa", "0101", "2023-12-01", PRIOR_RENT), lease("aaa", "0101", "2024-12-01", ASKING_RENT)]
    snapshot = snapshot_of(leases, [asking_row("aaa", "0101", "2024-12", ASKING_RENT)])
    growth = listing_growth(snapshot, loose_cfg)
    assert len(growth) == 1
    assert growth["asking_loggrowth"].iloc[0] > 0


def test_gap_outside_pair_bounds_is_dropped(loose_cfg):
    too_short = pd.Timestamp("2024-12-01") - pd.Timedelta(days=int(loose_cfg["pairs"]["min_gap_years"] * DAYS_PER_YEAR))
    leases = [lease("aaa", "0101", str(too_short.date()), PRIOR_RENT)]
    snapshot = snapshot_of(leases, [asking_row("aaa", "0101", "2024-12", ASKING_RENT)])
    assert listing_growth(snapshot, loose_cfg).empty


def test_signal_adds_spread_then_annualizes(hand_snapshot, loose_cfg):
    signal = turnover_signal(hand_snapshot, loose_cfg)
    assert list(signal.columns) == SIGNAL_COLUMNS
    gap = (pd.Timestamp("2024-12-01") - pd.Timestamp("2024-01-01")).days / DAYS_PER_YEAR
    row = signal.iloc[0]
    assert not row["is_renewal"]
    assert row["signal_source"] == SOURCE_SEGMENT
    assert row["expected_loggrowth_contract"] == pytest.approx(
        (math.log(ASKING_RENT / PRIOR_RENT) + math.log(SIGNED_RENT / PRIOR_RENT)) / gap)


def test_thin_segment_falls_back_to_province_pool(hand_snapshot, loose_cfg):
    loose_cfg["asking"]["min_listings_per_segment"] = 2
    signal = turnover_signal(hand_snapshot, loose_cfg)
    assert (signal["signal_source"] == SOURCE_PROVINCE).all()


@pytest.fixture(scope="module")
def synthetic_cutoff(cfg) -> pd.Timestamp:
    return cutoff_for(SYNTHETIC_FOLD_YEAR, cfg)


def test_synthetic_signal_matches_turnover_segments(tables, cfg, synthetic_cutoff):
    snapshot = make_snapshot(tables, pd.DataFrame(columns=["release_date"]), synthetic_cutoff)
    signal = turnover_signal(snapshot, cfg)
    weights = frozen_weights(training_pairs(snapshot, cfg), snapshot.cutoff, cfg)
    turnover_segments = weights.loc[~weights["is_renewal"], ["prop_code", "beds"]]
    assert len(signal) == len(turnover_segments)
    assert (~signal["is_renewal"]).all()
    assert signal["n_spread_leases"].gt(0).all()
    assert np.isfinite(signal.loc[signal["n_listings"] > 0, "expected_loggrowth_contract"]).all()


def test_future_asking_rows_do_not_change_the_signal(tables, cfg, synthetic_cutoff):
    external = pd.DataFrame(columns=["release_date"])
    baseline = turnover_signal(make_snapshot(tables, external, synthetic_cutoff), cfg)

    future = tables.asking.copy()
    future["month"] = future["month"] + (synthetic_cutoff.to_period("M") - future["month"].min()).n + 1
    future["asking_rent"] = future["asking_rent"] * FUTURE_RENT_MULTIPLIER
    leaked = copy.copy(tables)
    leaked.asking = pd.concat([tables.asking, future], ignore_index=True)
    after = turnover_signal(make_snapshot(leaked, external, synthetic_cutoff), cfg)
    pd.testing.assert_frame_equal(baseline, after)


def test_empty_asking_table_gives_empty_signal(hand_snapshot, cfg):
    """REQUEST-FCT-01: a snapshot with no asking rows returns an empty SIGNAL_COLUMNS table instead of crashing."""
    empty = copy.copy(hand_snapshot)
    empty.asking = hand_snapshot.asking.iloc[:0]
    signal = turnover_signal(empty, cfg)
    assert signal.empty
    assert list(signal.columns) == SIGNAL_COLUMNS
    assert signal["expected_loggrowth_contract"].dtype == float
