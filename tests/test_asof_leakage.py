"""Leakage tests for the as-of snapshot and the forecast.

Written before the implementation; the `make_snapshot` and `forecast` tests are hard tests.

Policy under test: the information-date rule. Cutoff for year y is December 31 of y-1; training uses leases with BOTH
sign_date and lease_start on/before the cutoff; asking months and concession date_from on/before the cutoff;
external rows by release_date; the listings snapshot is never used for historical folds.

Fixtures: committed synthetic data plus hand-made fake future rows. Never CRM data.
"""

from __future__ import annotations

import copy
from dataclasses import replace

import pandas as pd
import pytest

from halolens.config import cutoff_for
from halolens.contracts import EXTERNAL_COLUMNS, CanonicalTables
from halolens.forecast.asof import make_snapshot, snapshot_for_year
from halolens.forecast.combine import forecast


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
    combine = forecast_cfg["combine"]
    assert combine["renewal_history_weight"] + combine["renewal_nowcast_weight"] == pytest.approx(1.0)
    assert (combine["turnover_history_weight"] + combine["turnover_signal_weight"]
            + combine["turnover_nowcast_weight"]) == pytest.approx(1.0)
    assert set(forecast_cfg["scenarios"]) >= {"ontario_newbuild_guideline_applies", "include_post_cutoff_quebec_method"}
    assert isinstance(forecast_cfg["champion"]["top_n"], int) and forecast_cfg["champion"]["top_n"] > 0
    assert forecast_cfg["leakage_test"]["future_row_count"] > 0
    assert forecast_cfg["leakage_test"]["future_rent_multiplier"] > 1


def test_cutoff_is_december_31_of_previous_year(cfg):
    assert cutoff_for(2026, cfg) == pd.Timestamp("2025-12-31")
    assert cutoff_for(HISTORICAL_FOLD_YEAR, cfg) == pd.Timestamp("2024-12-31")


# ---------------------------------------------------------------------------
# make_snapshot
# ---------------------------------------------------------------------------
def test_snapshot_keeps_only_leases_signed_and_started_by_the_cutoff(tables, external, cutoff):
    snapshot = make_snapshot(tables, external, cutoff)
    assert snapshot.cutoff == cutoff
    assert len(snapshot.leases) > 0
    assert (snapshot.leases["sign_date"] <= cutoff).all()
    assert (snapshot.leases["lease_start"] <= cutoff).all()


def test_snapshot_cutoff_day_is_inclusive(tables, external, cutoff):
    """A lease signed and started exactly on the cutoff is knowable at the cutoff."""
    row = tables.leases.head(1).copy()
    row["sign_date"] = cutoff
    row["lease_start"] = cutoff
    row["lease_seq"] = row["lease_seq"] + 100
    with_boundary = replace(tables, leases=pd.concat([tables.leases, row], ignore_index=True))
    kept = make_snapshot(with_boundary, external, cutoff).leases
    assert len(kept) == len(make_snapshot(tables, external, cutoff).leases) + 1


def test_snapshot_drops_future_concessions_and_asking(tables, external, cutoff):
    snapshot = make_snapshot(tables, external, cutoff)
    assert (snapshot.concessions["date_from"] <= cutoff).all()
    assert (snapshot.asking["month"] <= cutoff.to_period("M")).all()
    assert len(snapshot.concessions) > 0 and len(snapshot.asking) > 0


def test_snapshot_rejects_post_cutoff_external_rows(tables, external, cutoff):
    snapshot = make_snapshot(tables, external, cutoff)
    assert set(snapshot.external["series_id"]) == {"test_before"}
    assert (snapshot.external["release_date"] <= cutoff).all()


def test_snapshot_never_uses_listings_for_a_historical_fold(tables, external, cutoff):
    """The listings table is a 2025 snapshot: unusable for any cutoff before the end of the data."""
    assert make_snapshot(tables, external, cutoff).units is None


def test_snapshot_does_not_modify_its_inputs(tables, external, cutoff):
    leases_before, external_before = tables.leases.copy(), external.copy()
    make_snapshot(tables, external, cutoff)
    pd.testing.assert_frame_equal(tables.leases, leases_before)
    pd.testing.assert_frame_equal(external, external_before)


def test_appending_future_rows_leaves_the_snapshot_identical(tables, external, cutoff, cfg):
    """Core leakage test: fake rows dated after the cutoff must not change anything inside the snapshot."""
    future = fake_future_tables(tables, cutoff, cfg)
    assert len(future.leases) > len(tables.leases)   # the fake rows really were appended
    future_external = pd.concat([external, external.assign(series_id="test_later", release_date=cutoff + ONE_DAY * 90)],
                                ignore_index=True)
    assert_same_snapshot(make_snapshot(tables, external, cutoff),
                         make_snapshot(future, future_external, cutoff))


# ---------------------------------------------------------------------------
# forecast
# ---------------------------------------------------------------------------
def test_appending_future_rows_leaves_the_forecast_identical(tables, external, cutoff, cfg):
    """Same forecast whether or not post-cutoff rows exist in the source tables."""
    future = fake_future_tables(tables, cutoff, cfg)
    base = forecast(make_snapshot(tables, external, cutoff), copy.deepcopy(cfg))
    leaked = forecast(make_snapshot(future, external, cutoff), copy.deepcopy(cfg))
    assert leaked.headline_net_pct == base.headline_net_pct
    assert leaked.headline_contract_pct == base.headline_contract_pct
    assert leaked.median_net_pct == base.median_net_pct
    pd.testing.assert_frame_equal(fingerprint(leaked.segments), fingerprint(base.segments))


# ---------------------------------------------------------------------------
# External information date (information-date rule): public data by Jan 31 of the target year, CRM data by Dec 31
# ---------------------------------------------------------------------------
JAN_31 = pd.Timestamp("2025-01-31")   # external cutoff for the 2025 fold (CRM cutoff 2024-12-31)


@pytest.fixture(scope="module")
def external_by_release(cutoff) -> pd.DataFrame:
    """Hand-made rows released on the CRM cutoff, in January, on Jan 31 and in February of the target year."""
    releases = {"on_cutoff": cutoff, "mid_january": pd.Timestamp("2025-01-15"), "on_jan_31": JAN_31,
                "in_february": pd.Timestamp("2025-02-01")}
    rows = [{"series_id": name, "publisher": "test", "geography": "QC", "metric": "rent_cpi", "unit": "pct",
             "ref_period_start": pd.Timestamp("2024-01-01"), "ref_period_end": pd.Timestamp("2024-12-31"),
             "value": 2.0, "release_date": release} for name, release in releases.items()]
    frame = pd.DataFrame(rows).reindex(columns=EXTERNAL_COLUMNS)
    for column in ["ref_period_start", "ref_period_end", "release_date"]:
        frame[column] = pd.to_datetime(frame[column])
    return frame


def test_external_row_released_after_the_external_cutoff_is_rejected(tables, external_by_release, cutoff):
    snapshot = make_snapshot(tables, external_by_release, cutoff, external_cutoff=JAN_31)
    assert "in_february" not in set(snapshot.external["series_id"])
    assert (snapshot.external["release_date"] <= JAN_31).all()


def test_external_row_released_between_the_two_cutoffs_is_accepted(tables, external_by_release, cutoff):
    snapshot = make_snapshot(tables, external_by_release, cutoff, external_cutoff=JAN_31)
    assert {"mid_january", "on_jan_31"} <= set(snapshot.external["series_id"])    # external cutoff day is inclusive
    assert cutoff < pd.Timestamp("2025-01-15") <= JAN_31


def test_crm_rows_after_the_crm_cutoff_are_still_rejected_with_a_later_external_cutoff(tables, external, cutoff, cfg):
    future = fake_future_tables(tables, cutoff, cfg)
    snapshot = make_snapshot(future, external, cutoff, external_cutoff=JAN_31)
    assert (snapshot.leases["sign_date"] <= cutoff).all() and (snapshot.leases["lease_start"] <= cutoff).all()
    assert (snapshot.concessions["date_from"] <= cutoff).all()
    assert (snapshot.asking["month"] <= cutoff.to_period("M")).all()
    assert_same_snapshot(snapshot, make_snapshot(tables, external, cutoff, external_cutoff=JAN_31))


def test_external_cutoff_equal_to_the_crm_cutoff_is_the_strict_dec_31_version(tables, external_by_release, cutoff):
    strict = make_snapshot(tables, external_by_release, cutoff, external_cutoff=cutoff)
    default = make_snapshot(tables, external_by_release, cutoff)
    assert_same_snapshot(strict, default)
    assert set(strict.external["series_id"]) == {"on_cutoff"}


def test_default_external_cutoff_behaves_as_before(tables, external, cutoff):
    assert_same_snapshot(make_snapshot(tables, external, cutoff), make_snapshot(tables, external, cutoff, None))


def test_snapshot_for_year_uses_dec_31_for_crm_and_jan_31_for_public_data(tables, external_by_release, cfg):
    snapshot = snapshot_for_year(tables, external_by_release, HISTORICAL_FOLD_YEAR, cfg)
    assert snapshot.cutoff == pd.Timestamp("2024-12-31")
    assert (snapshot.leases["lease_start"] <= snapshot.cutoff).all()
    assert set(snapshot.external["series_id"]) == {"on_cutoff", "mid_january", "on_jan_31"}


def test_snapshot_for_year_strict_flag_gives_the_dec_31_sensitivity(tables, external_by_release, cfg):
    snapshot = snapshot_for_year(tables, external_by_release, HISTORICAL_FOLD_YEAR, cfg, strict=True)
    assert set(snapshot.external["series_id"]) == {"on_cutoff"}


def test_forecast_is_unchanged_by_public_data_released_after_the_external_cutoff(tables, external_by_release, cutoff, cfg):
    """A February release can move nothing; a mid-January one is allowed to (it is inside the agreed window)."""
    later = pd.concat([external_by_release, external_by_release.assign(series_id="much_later", value=99.0,
                                                                        release_date=pd.Timestamp("2025-03-01"))],
                      ignore_index=True)
    base = forecast(make_snapshot(tables, external_by_release, cutoff, external_cutoff=JAN_31), copy.deepcopy(cfg))
    leaked = forecast(make_snapshot(tables, later, cutoff, external_cutoff=JAN_31), copy.deepcopy(cfg))
    assert leaked.headline_net_pct == base.headline_net_pct
