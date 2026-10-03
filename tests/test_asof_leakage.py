"""Leakage tests for the as-of snapshot and the forecast. Owner: FCT.

Written in F-01 before the implementation (F-02 `make_snapshot`, F-05 `forecast`). Tests that call them are marked
`expected_until_f02` / `expected_until_f05`: they fail with NotImplementedError today and turn into hard failures the
moment the function exists, so the task that implements it must remove the marker. Config tests pass now.

Policy under test: AGENTS.md Section 9.3. Cutoff for year y is December 31 of y-1; training uses leases with BOTH
sign_date and lease_start on/before the cutoff; asking months and concession date_from on/before the cutoff;
external rows by release_date; the listings snapshot is never used for historical folds.

Fixtures: committed synthetic data plus hand-made fake future rows. Never CRM data.
"""

from __future__ import annotations

import copy
from dataclasses import replace

import pandas as pd
import pytest

from leaselens.config import cutoff_for
from leaselens.contracts import EXTERNAL_COLUMNS, CanonicalTables
from leaselens.forecast.asof import make_snapshot
from leaselens.forecast.combine import forecast

expected_until_f02 = pytest.mark.xfail(raises=NotImplementedError, strict=True,
                                       reason="make_snapshot is implemented in F-02")
expected_until_f05 = pytest.mark.xfail(raises=NotImplementedError, strict=True,
                                       reason="forecast is implemented in F-05")

HISTORICAL_FOLD_YEAR = 2025   # cutoff 2024-12-31: the synthetic data has plenty of rows after it
ONE_DAY = pd.Timedelta(days=1)
SIGN_LAG = pd.Timedelta(days=30)   # fake leases start this long after they are signed


@pytest.fixture(scope="module")
def cutoff(cfg) -> pd.Timestamp:
    return cutoff_for(HISTORICAL_FOLD_YEAR, cfg)


@pytest.fixture(scope="module")
def external(cutoff) -> pd.DataFrame:
    """Two hand-made external observations: one released before the cutoff, one after."""
    rows = [
        {"series_id": "test_before", "publisher": "test", "geography": "QC", "metric": "rent_cpi", "unit": "pct",
         "ref_period_start": cutoff - 365 * ONE_DAY, "ref_period_end": cutoff - 335 * ONE_DAY, "value": 2.0,
         "release_date": cutoff - 10 * ONE_DAY},
        {"series_id": "test_after", "publisher": "test", "geography": "QC", "metric": "rent_cpi", "unit": "pct",
         "ref_period_start": cutoff - 30 * ONE_DAY, "ref_period_end": cutoff, "value": 9.9,
         "release_date": cutoff + 10 * ONE_DAY},
    ]
    frame = pd.DataFrame(rows).reindex(columns=EXTERNAL_COLUMNS)
    for column in ["ref_period_start", "ref_period_end", "release_date"]:
        frame[column] = pd.to_datetime(frame[column])
    return frame


def fake_future_tables(tables: CanonicalTables, cutoff: pd.Timestamp, cfg: dict) -> CanonicalTables:
    """Copy of `tables` with fake rows appended that are NOT knowable at `cutoff`, with exaggerated values."""
    count = cfg["leakage_test"]["future_row_count"]
    factor = cfg["leakage_test"]["future_rent_multiplier"]

    leases = tables.leases.head(count).copy()
    leases["sign_date"] = cutoff + ONE_DAY * 10
    leases["lease_start"] = leases["sign_date"] + SIGN_LAG
    leases["lease_end"] = leases["lease_start"] + pd.DateOffset(years=1)
    leases["lease_seq"] = leases["lease_seq"] + 100
    leases["rent_contract"] = leases["rent_contract"] * factor
    leases["rent_net_all_incentives"] = leases["rent_net_all_incentives"] * factor

    # Signed before the cutoff but starting after it: still not training data (both dates must be <= cutoff).
    signed_early = leases.copy()
    signed_early["sign_date"] = cutoff - ONE_DAY * 5

    concessions = tables.concessions.head(count).copy()
    concessions["concession_id"] = concessions["concession_id"] + 10_000
    concessions["date_from"] = cutoff + ONE_DAY * 10
    concessions["credit_amount"] = concessions["credit_amount"] * factor

    asking = tables.asking.head(count).copy()
    asking["month"] = (cutoff + ONE_DAY * 40).to_period("M")
    asking["asking_rent"] = asking["asking_rent"] * factor

    return CanonicalTables(
        leases=pd.concat([tables.leases, leases, signed_early], ignore_index=True),
        concessions=pd.concat([tables.concessions, concessions], ignore_index=True),
        asking=pd.concat([tables.asking, asking], ignore_index=True),
        units=tables.units,
    )


def fingerprint(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    """Order- and index-independent form of a table, for equality checks."""
    if frame is None:
        return None
    return frame.sort_values(list(frame.columns), kind="stable").reset_index(drop=True)


def assert_same_snapshot(left, right) -> None:
    assert left.cutoff == right.cutoff
    for name in ["leases", "concessions", "asking", "units", "external"]:
        a, b = fingerprint(getattr(left, name)), fingerprint(getattr(right, name))
        if a is None or b is None:
            assert a is None and b is None, f"{name}: one snapshot has it, the other does not"
        else:
            pd.testing.assert_frame_equal(a, b, check_dtype=False)


# ---------------------------------------------------------------------------
# Fixture sanity and config (pass today)
# ---------------------------------------------------------------------------
def test_synthetic_data_has_rows_after_the_cutoff(tables, cutoff):
    """Without post-cutoff rows the leakage tests below would prove nothing."""
    assert (tables.leases["lease_start"] > cutoff).any()
    assert (tables.leases["sign_date"] > cutoff).any()
    assert (tables.concessions["date_from"] > cutoff).any()
    assert (tables.asking["month"] > cutoff.to_period("M")).any()


def test_synthetic_data_has_leases_signed_before_but_starting_after_the_cutoff(tables, cutoff):
    """The both-dates rule only matters if such leases exist."""
    straddling = (tables.leases["sign_date"] <= cutoff) & (tables.leases["lease_start"] > cutoff)
    assert straddling.any()


def test_forecast_config_has_agreed_keys(cfg):
    forecast_cfg = cfg  # merged config: forecast.yaml keys sit at the top level
    assert forecast_cfg["baselines"]["trailing_window_years"] > 0
    assert forecast_cfg["incentives"]["trend_window_years"] > 0
    assert forecast_cfg["nowcast"]["min_pairs_per_month"] > 0
    assert forecast_cfg["selection"]["metric"]
    weights = forecast_cfg["combine"]
    assert weights["renewal_engine_weight"] + weights["turnover_engine_weight"] == pytest.approx(1.0)
    assert set(forecast_cfg["scenarios"]) >= {"met_guideline_applies", "include_post_cutoff_quebec_method"}
    assert forecast_cfg["leakage_test"]["future_row_count"] > 0
    assert forecast_cfg["leakage_test"]["future_rent_multiplier"] > 1


def test_cutoff_is_december_31_of_previous_year(cfg):
    assert cutoff_for(2026, cfg) == pd.Timestamp("2025-12-31")
    assert cutoff_for(HISTORICAL_FOLD_YEAR, cfg) == pd.Timestamp("2024-12-31")


# ---------------------------------------------------------------------------
# make_snapshot (F-02)
# ---------------------------------------------------------------------------
@expected_until_f02
def test_snapshot_keeps_only_leases_signed_and_started_by_the_cutoff(tables, external, cutoff):
    snapshot = make_snapshot(tables, external, cutoff)
    assert snapshot.cutoff == cutoff
    assert len(snapshot.leases) > 0
    assert (snapshot.leases["sign_date"] <= cutoff).all()
    assert (snapshot.leases["lease_start"] <= cutoff).all()


@expected_until_f02
def test_snapshot_cutoff_day_is_inclusive(tables, external, cutoff):
    """A lease signed and started exactly on the cutoff is knowable at the cutoff."""
    row = tables.leases.head(1).copy()
    row["sign_date"] = cutoff
    row["lease_start"] = cutoff
    row["lease_seq"] = row["lease_seq"] + 100
    with_boundary = replace(tables, leases=pd.concat([tables.leases, row], ignore_index=True))
    kept = make_snapshot(with_boundary, external, cutoff).leases
    assert len(kept) == len(make_snapshot(tables, external, cutoff).leases) + 1


@expected_until_f02
def test_snapshot_drops_future_concessions_and_asking(tables, external, cutoff):
    snapshot = make_snapshot(tables, external, cutoff)
    assert (snapshot.concessions["date_from"] <= cutoff).all()
    assert (snapshot.asking["month"] <= cutoff.to_period("M")).all()
    assert len(snapshot.concessions) > 0 and len(snapshot.asking) > 0


@expected_until_f02
def test_snapshot_rejects_post_cutoff_external_rows(tables, external, cutoff):
    snapshot = make_snapshot(tables, external, cutoff)
    assert set(snapshot.external["series_id"]) == {"test_before"}
    assert (snapshot.external["release_date"] <= cutoff).all()


@expected_until_f02
def test_snapshot_never_uses_listings_for_a_historical_fold(tables, external, cutoff):
    """The listings table is a 2025 snapshot: unusable for any cutoff before the end of the data."""
    assert make_snapshot(tables, external, cutoff).units is None


@expected_until_f02
def test_snapshot_does_not_modify_its_inputs(tables, external, cutoff):
    leases_before, external_before = tables.leases.copy(), external.copy()
    make_snapshot(tables, external, cutoff)
    pd.testing.assert_frame_equal(tables.leases, leases_before)
    pd.testing.assert_frame_equal(external, external_before)


@expected_until_f02
def test_appending_future_rows_leaves_the_snapshot_identical(tables, external, cutoff, cfg):
    """Core leakage test: fake rows dated after the cutoff must not change anything inside the snapshot."""
    future = fake_future_tables(tables, cutoff, cfg)
    assert len(future.leases) > len(tables.leases)   # the fake rows really were appended
    future_external = pd.concat([external, external.assign(series_id="test_later", release_date=cutoff + ONE_DAY * 90)],
                                ignore_index=True)
    assert_same_snapshot(make_snapshot(tables, external, cutoff),
                         make_snapshot(future, future_external, cutoff))


# ---------------------------------------------------------------------------
# forecast (F-05)
# ---------------------------------------------------------------------------
@expected_until_f05
def test_appending_future_rows_leaves_the_forecast_identical(tables, external, cutoff, cfg):
    """Same forecast whether or not post-cutoff rows exist in the source tables."""
    future = fake_future_tables(tables, cutoff, cfg)
    base = forecast(make_snapshot(tables, external, cutoff), copy.deepcopy(cfg))
    leaked = forecast(make_snapshot(future, external, cutoff), copy.deepcopy(cfg))
    assert leaked.headline_net_pct == base.headline_net_pct
    assert leaked.headline_contract_pct == base.headline_contract_pct
    assert leaked.median_net_pct == base.median_net_pct
    pd.testing.assert_frame_equal(fingerprint(leaked.segments), fingerprint(base.segments))
