"""Tests for the unit-cluster bootstrap (evaluate.uncertainty).

Fixtures: the committed synthetic data and hand-made leases with known growth. No CRM data.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from halolens.evaluate.backtest import champion_pipeline, empty_external
from halolens.evaluate.uncertainty import (COPY_SEPARATOR, DRAW_COLUMNS, bootstrap_interval, resample_units,
                                            unit_bootstrap)
from halolens.forecast.asof import snapshot_for_year
from halolens.forecast.baselines import last_year
from tests.test_baselines import annual_leases, tables_from

N_DRAWS = 25
CONSTANT_GROWTH = {year: 0.04 for year in range(2020, 2026)}
MANY_UNITS = [(f"p{p}", "QC", f"{u:04d}") for p in range(2) for u in range(8)]


@pytest.fixture(scope="module")
def draws(tables, cfg):
    return unit_bootstrap(tables, empty_external(), cfg, N_DRAWS, champion="B0_last_year")


# ---------------------------------------------------------------------------
# Resampling: whole unit histories, not leases
# ---------------------------------------------------------------------------
def test_a_draw_resamples_units_not_leases(tables):
    sample = resample_units(tables, np.random.default_rng(1))
    original_sizes = tables.leases.groupby("unit_id").size()
    sampled_sizes = sample.leases.groupby("unit_id").size()
    source = sampled_sizes.index.str.split(COPY_SEPARATOR).str[0]
    assert (sampled_sizes.to_numpy() == original_sizes.loc[source].to_numpy()).all()   # every copy keeps its full history
    assert sample.leases["unit_id"].nunique() == tables.leases["unit_id"].nunique()      # as many units as the original
    other = resample_units(tables, np.random.default_rng(99))
    assert len(sample.leases) != len(other.leases) or len(sample.leases) != len(tables.leases)   # lease count varies by draw


def test_each_copy_carries_the_exact_lease_history_of_its_source_unit(tables):
    sample = resample_units(tables, np.random.default_rng(2))
    columns = ["lease_seq", "lease_start", "rent_contract", "rent_net_all_incentives", "is_renewal"]
    for new_id, group in list(sample.leases.groupby("unit_id"))[:15]:
        source_id = new_id.split(COPY_SEPARATOR)[0]
        original = tables.leases[tables.leases["unit_id"] == source_id].sort_values("lease_seq")
        pd.testing.assert_frame_equal(group.sort_values("lease_seq")[columns].reset_index(drop=True),
                                      original[columns].reset_index(drop=True))


def test_a_unit_drawn_twice_becomes_two_distinct_units(tables):
    sample = resample_units(tables, np.random.default_rng(3))
    base_ids = sample.leases["unit_id"].str.split(COPY_SEPARATOR).str[0]
    assert base_ids.nunique() < sample.leases["unit_id"].nunique()                       # some unit was drawn more than once
    codes = sample.leases.drop_duplicates("unit_id")[["prop_code", "unit_code", "unit_id"]]
    assert not codes.duplicated(["prop_code", "unit_code"]).any()                        # the safe key stays one-to-one
    assert codes["unit_code"].str.contains(COPY_SEPARATOR).all()


def test_concessions_and_asking_travel_with_their_unit(tables):
    sample = resample_units(tables, np.random.default_rng(4))
    assert set(sample.concessions["unit_id"]) <= set(sample.leases["unit_id"])
    assert set(sample.asking["unit_id"]) <= set(sample.leases["unit_id"])
    first = sample.concessions["unit_id"].iloc[0]
    source = first.split(COPY_SEPARATOR)[0]
    assert (tables.concessions["unit_id"] == source).sum() == (sample.concessions["unit_id"] == first).sum()


def test_resampling_does_not_modify_the_input_tables(tables):
    leases_before, asking_before = tables.leases.copy(), tables.asking.copy()
    resample_units(tables, np.random.default_rng(5))
    pd.testing.assert_frame_equal(tables.leases, leases_before)
    pd.testing.assert_frame_equal(tables.asking, asking_before)


def test_resampled_samples_still_build_valid_pairs(tables, cfg):
    """The relabelled copies keep consecutive leases of one unit together, so pairs are built within each copy."""
    from halolens.measure.pairs import build_pairs
    original = build_pairs(tables.leases, cfg)
    sample = build_pairs(resample_units(tables, np.random.default_rng(6)).leases, cfg)
    assert 0.5 * len(original) < len(sample) < 1.6 * len(original)
    assert set(sample["exclusion_reason"]) <= set(original["exclusion_reason"]) | {""}


# ---------------------------------------------------------------------------
# Reproducibility, structure and the interval
# ---------------------------------------------------------------------------
def test_the_fixed_seed_reproduces_the_draws(tables, cfg, draws):
    again = unit_bootstrap(tables, empty_external(), cfg, N_DRAWS, champion="B0_last_year")
    pd.testing.assert_frame_equal(draws, again)


def test_another_seed_gives_other_draws(tables, cfg, draws):
    other = unit_bootstrap(tables, empty_external(), {**cfg, "random_seed": cfg["random_seed"] + 1}, N_DRAWS,
                           champion="B0_last_year")
    assert not np.allclose(other["net_pct"], draws["net_pct"])


def test_a_draw_does_not_depend_on_how_many_draws_are_requested(tables, cfg, draws):
    few = unit_bootstrap(tables, empty_external(), cfg, 5, champion="B0_last_year")
    pd.testing.assert_frame_equal(few, draws.head(5))


def test_draw_table_has_the_agreed_columns_and_no_unit_identifiers(draws):
    assert list(draws.columns) == DRAW_COLUMNS and len(draws) == N_DRAWS
    assert draws["draw"].tolist() == list(range(N_DRAWS))
    assert draws["net_pct"].notna().all() and (draws["model"] == "B0_last_year").all()
    assert not draws.astype(str).apply(lambda column: column.str.contains(COPY_SEPARATOR)).any().any()


def test_interval_uses_the_configured_quantiles_and_contains_the_point_estimate(tables, cfg, draws):
    point = last_year(snapshot_for_year(tables, empty_external(), 2026, cfg), cfg)
    summary = bootstrap_interval(draws, cfg)
    low, high = cfg["uncertainty"]["interval_quantiles"]
    assert summary["quantiles"] == [low, high] and summary["n_ok"] == N_DRAWS and summary["n_failed"] == 0
    assert summary["net_pct"]["lower"] == pytest.approx(draws["net_pct"].quantile(low))
    assert summary["net_pct"]["upper"] == pytest.approx(draws["net_pct"].quantile(high))
    assert summary["net_pct"]["lower"] < summary["net_pct"]["upper"]
    assert summary["net_pct"]["lower"] <= point.headline_net_pct <= summary["net_pct"]["upper"]
    assert summary["contract_pct"]["lower"] <= point.headline_contract_pct <= summary["contract_pct"]["upper"]


def test_interval_is_degenerate_when_every_unit_has_the_same_growth(cfg):
    tables = tables_from(annual_leases(CONSTANT_GROWTH, units=MANY_UNITS))
    result = unit_bootstrap(tables, empty_external(), cfg, 10, champion="B0_last_year", year=2025)
    summary = bootstrap_interval(result, cfg)
    point = 100 * np.expm1(np.log1p(0.04))
    assert summary["net_pct"]["lower"] == pytest.approx(point, abs=0.05) == pytest.approx(summary["net_pct"]["upper"], abs=0.05)
    assert summary["net_pct"]["sd"] < 0.05


def test_failed_draws_keep_their_row_with_the_reason_and_are_counted(tables, cfg):
    calls = {"count": 0}

    def flaky(snapshot, cfg_):
        calls["count"] += 1
        if calls["count"] % 2 == 0:
            raise ValueError("no usable pairs in this draw")
        return last_year(snapshot, cfg_)

    result = unit_bootstrap(tables, empty_external(), cfg, 6, champion="flaky", models={"flaky": flaky})
    assert result["note"].ne("").sum() == 3 and result[result["note"] != ""]["net_pct"].isna().all()
    summary = bootstrap_interval(result, cfg)
    assert summary["n_failed"] == 3 and summary["n_ok"] == 3


def test_interval_on_no_successful_draw_is_nan(cfg):
    empty = pd.DataFrame(columns=DRAW_COLUMNS)
    summary = bootstrap_interval(empty, cfg)
    assert summary["n_ok"] == 0 and np.isnan(summary["net_pct"]["lower"])


def test_default_champion_is_the_pre_declared_choice_and_the_config_is_untouched(tables, cfg):
    before = copy.deepcopy(cfg)
    result = unit_bootstrap(tables, empty_external(), cfg, 3)
    assert (result["model"] == champion_pipeline(tables, empty_external(), cfg)["champion"]).all()
    assert cfg == before


def test_bootstrap_runs_for_an_engine_champion_too(tables, cfg):
    from tests.test_combine import regulated_rows
    external = regulated_rows({y: 2.0 for y in range(2019, 2027)}, {y: 2.5 for y in range(2019, 2027)})
    result = unit_bootstrap(tables, external, cfg, 3, champion="E1_engine_blend")
    assert result["net_pct"].notna().all()
