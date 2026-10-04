"""Tests for the aggregate export (I-09). Owner: INT.

Synthetic fixtures only (conftest). The public sources file supplies the external table; it holds no CRM data.
Headline tests are skipped until F-08's champion pipeline is merged (TODO(F-08) in export/aggregates.py).
"""

from __future__ import annotations

import copy
import json

import jsonschema
import pytest
from jsonschema import Draft202012Validator, FormatChecker

from leaselens.config import cutoff_for, external_cutoff_for, repo_root
from leaselens.contracts import AGGREGATES_SCHEMA
from leaselens.evaluate.backtest import all_models
from leaselens.export.aggregates import DEFINITION, build_aggregates, export
from leaselens.market.registry import load_external
from leaselens.measure.pairs import build_pairs

F08_REASON = "TODO(F-08): headline comes from champion_forecast, which lands with PR #32 (FCT F-08)"


@pytest.fixture(scope="module")
def external():
    return load_external(repo_root() / "data" / "public" / "sources.csv")


@pytest.fixture(scope="module")
def document(tables, cfg, external):
    return build_aggregates(tables, external, cfg)


def _identifiers(tables) -> set[str]:
    leases = tables.leases
    values: set[str] = set()
    for column in ("unit_id", "prop_code", "unit_code"):
        values |= {str(value) for value in leases[column].dropna().unique()}
    return values


def test_document_validates_against_the_schema(document):
    assert list(Draft202012Validator(AGGREGATES_SCHEMA, format_checker=FormatChecker()).iter_errors(document)) == []


def test_document_is_marked_synthetic_on_synthetic_data(document):
    assert document["mode"] == "synthetic"
    assert "SYNTHÉTIQUE" in document["note"]


def test_no_unit_level_identifier_appears_anywhere(document, tables):
    text = json.dumps(document, ensure_ascii=False)
    for identifier in _identifiers(tables):
        assert f'"{identifier}"' not in text, "a unit-level identifier leaked into the aggregates"
    lowered = text.lower()
    for token in ("hunit", "sunitcode", "spropcode", "unit_id", "unit_code", "prop_code", "address"):
        assert token not in lowered, token


def test_coverage_counts_match_the_pairs_table(document, tables, cfg):
    pairs = build_pairs(tables.leases, cfg)
    coverage = document["coverage"]
    assert coverage["leases"] == len(tables.leases)
    assert coverage["eligible_pairs"] == int(pairs["eligible"].sum())
    assert coverage["eligible_pairs"] + coverage["excluded_pairs"] == len(pairs)
    assert coverage["concessions"] == len(tables.concessions)
    assert coverage["asking_rows"] == len(tables.asking)


def test_backtest_has_every_model_year_and_rule(document, cfg):
    years = cfg["forecast_years"]["backtest_years"]
    rules = 2 if cfg["forecast_years"]["external_cutoff_strict_sensitivity"] else 1
    rows = document["backtest"]
    assert len(rows) == len(all_models()) * len(years) * rules
    assert {row["model"] for row in rows} == set(all_models())
    assert {row["year"] for row in rows} == set(years)


def test_backtest_error_is_forecast_minus_actual(document):
    for row in document["backtest"]:
        if row["forecast_net_pct"] is None:
            assert row["error_pp_net"] is None  # a failed fold keeps no numbers
            continue
        assert row["error_pp_net"] == pytest.approx(row["forecast_net_pct"] - row["actual_net_pct"], abs=1e-9)
        assert row["error_pp_contract"] == pytest.approx(
            row["forecast_contract_pct"] - row["actual_contract_pct"], abs=1e-9)


def test_scenario_range_is_ordered(document):
    scenarios = document["scenarios"]
    assert scenarios["low_net_pct"] <= scenarios["central_net_pct"] <= scenarios["high_net_pct"]


def test_as_of_dates_follow_the_information_rules(document, cfg):
    target = cfg["forecast_years"]["target_year"]
    assert document["as_of"]["crm_cutoff"] == cutoff_for(target, cfg).date().isoformat()
    assert document["as_of"]["external_cutoff"] == external_cutoff_for(target, cfg).date().isoformat()


def test_sources_are_public_metadata_released_by_the_cutoff(document, cfg):
    cutoff = external_cutoff_for(cfg["forecast_years"]["target_year"], cfg).date().isoformat()
    assert document["sources"]
    for source in document["sources"]:
        assert set(source) == {"series_id", "publisher", "url", "release_date"}
        assert source["url"].startswith("http")
        assert source["release_date"] <= cutoff


def test_definition_is_the_agreed_text(document):
    assert document["definition"] == DEFINITION
    assert "composition fixe" in document["definition"]


def test_export_writes_a_valid_file(document, tmp_path):
    path = tmp_path / "nested" / "aggregates.json"
    export(document, path)
    assert json.loads(path.read_text(encoding="utf-8")) == document


def test_export_refuses_a_unit_level_field_and_writes_nothing(document, tmp_path):
    tampered = copy.deepcopy(document)
    tampered["units"] = [{"unit_id": "123"}]
    path = tmp_path / "aggregates.json"
    with pytest.raises(jsonschema.ValidationError):
        export(tampered, path)
    assert not path.exists()


@pytest.mark.skip(reason=F08_REASON)
def test_headline_equals_estimate_2026(document):
    """Headline net and contract must equal estimate_2026() on the same data (same champion pipeline)."""


@pytest.mark.skip(reason=F08_REASON)
def test_headline_model_is_the_declared_champion(document):
    """The headline model is the champion selected by the rule declared before results."""


@pytest.mark.skip(reason=F08_REASON)
def test_model_range_covers_the_candidate_models(document):
    """The 2026 model range is the min and max over B0, B1, E1 and E2 under the January-31 rule."""
