"""Each model forced as champion: the export validates and the section 00 and 10 code paths do not raise. Owner: INT.

Synthetic fixtures only. `select_champion` is patched to name the forced model while keeping the real ranking, so the
paths that read the ranking (section 00) and the champion forecast (sections 00 and 10) run exactly as in the notebook.
The backtest table is computed once and shared, because it does not depend on which model is named champion.
"""

from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator, FormatChecker

import leaselens.evaluate.backtest as backtest_module
import leaselens.export.aggregates as aggregates_module
from leaselens.config import repo_root
from leaselens.contracts import AGGREGATES_SCHEMA
from leaselens.evaluate.backtest import (all_models, backtest_both_rules, champion_backtest, champion_forecast,
                                         champion_pipeline, tables_from_leases)
from leaselens.export.aggregates import build_aggregates
from leaselens.market.registry import load_external

MODELS = sorted(all_models())


@pytest.fixture(scope="module")
def external():
    return load_external(repo_root() / "data" / "public" / "sources.csv")


@pytest.fixture(scope="module")
def shared_table(tables, external, cfg):
    return backtest_both_rules(tables, external, cfg)


def test_the_six_models_are_the_expected_ones():
    assert len(MODELS) == 6
    assert {name[:2] for name in MODELS} == {"B0", "B1", "B2", "B3", "E1", "E2"}


@pytest.mark.parametrize("forced", MODELS)
def test_forced_champion_export_validates_and_notebook_paths_run(monkeypatch, forced, tables, external, cfg,
                                                                  shared_table):
    real_select = backtest_module.select_champion
    monkeypatch.setattr(backtest_module, "select_champion",
                        lambda table, config: {**real_select(table, config), "champion": forced})
    monkeypatch.setattr(aggregates_module, "backtest_both_rules", lambda *args, **kwargs: shared_table)

    document = build_aggregates(tables, external, cfg)
    assert list(Draft202012Validator(AGGREGATES_SCHEMA, format_checker=FormatChecker()).iter_errors(document)) == []
    assert document["headline"]["model"] == forced
    assert document["headline"]["net_pct"] is not None

    # section 00 reads the ranking and the champion row; section 10 calls the champion pipeline through the wrappers
    pipeline = champion_pipeline(tables, external, cfg, table=shared_table)
    assert pipeline["champion"] == forced
    assert forced in set(pipeline["ranking"]["model"])
    estimate = champion_forecast(tables_from_leases(tables.leases, tables.asking), external, cfg, table=shared_table)
    assert estimate.headline_net_pct == pytest.approx(document["headline"]["net_pct"])
    fold = champion_backtest(tables_from_leases(tables.leases, tables.asking), external,
                             cfg["forecast_years"]["holdout_year"], cfg, table=shared_table)
    assert fold.forecast.model_name
