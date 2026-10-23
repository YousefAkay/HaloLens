"""Tests for AGGREGATES_SCHEMA and the synthetic example.

The schema is the contract for the only file the app and the narrative read. These tests check that the
example conforms, that the schema is closed (no unit-level field can be added), and that backtest errors
follow the forecast minus actual convention.
"""

from __future__ import annotations

import copy
import json

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from halolens.config import repo_root
from halolens.contracts import AGGREGATES_SCHEMA, INFORMATION_RULES, MODES

EXAMPLE = repo_root() / "outputs" / "public" / "aggregates_synthetic.json"
UNIT_LEVEL_TOKENS = ("hunit", "sunitcode", "spropcode", "unit_id", "unit_code", "prop_code", "unit")


def _validator() -> Draft202012Validator:
    return Draft202012Validator(AGGREGATES_SCHEMA, format_checker=FormatChecker())


@pytest.fixture
def example() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _all_keys(node) -> list[str]:
    if isinstance(node, dict):
        return [key for child in node.values() for key in [*node.keys(), *_all_keys(child)]]
    if isinstance(node, list):
        return [key for child in node for key in _all_keys(child)]
    return []


def test_schema_is_a_valid_draft_2020_12_schema():
    Draft202012Validator.check_schema(AGGREGATES_SCHEMA)


def test_example_validates_against_schema(example):
    assert list(_validator().iter_errors(example)) == []


def test_example_is_marked_synthetic(example):
    assert example["mode"] == "synthetic"
    assert "SYNTHÉTIQUE" in example["note"]


def test_backtest_errors_are_forecast_minus_actual(example):
    for row in example["backtest"]:
        assert row["error_pp_net"] == pytest.approx(row["forecast_net_pct"] - row["actual_net_pct"], abs=1e-9)
        assert row["error_pp_contract"] == pytest.approx(
            row["forecast_contract_pct"] - row["actual_contract_pct"], abs=1e-9)


def test_example_has_no_unit_level_identifiers(example):
    keys = {key.lower() for key in _all_keys(example)}
    assert not keys & set(UNIT_LEVEL_TOKENS), keys & set(UNIT_LEVEL_TOKENS)
    text = json.dumps(example).lower()
    assert "hunit" not in text and "sunitcode" not in text and "spropcode" not in text


def test_unit_level_field_is_rejected(example):
    tampered = copy.deepcopy(example)
    tampered["units"] = [{"unit_id": "123"}]
    assert list(_validator().iter_errors(tampered))


def test_unknown_information_rule_is_rejected(example):
    tampered = copy.deepcopy(example)
    tampered["headline"]["information_rule"] = "dec30"
    assert list(_validator().iter_errors(tampered))


def test_missing_required_field_is_rejected(example):
    tampered = copy.deepcopy(example)
    del tampered["note"]
    assert list(_validator().iter_errors(tampered))


def test_schema_version_is_pinned(example):
    tampered = copy.deepcopy(example)
    tampered["schema_version"] = 3
    assert list(_validator().iter_errors(tampered))


def test_enums_match_the_documented_values():
    assert INFORMATION_RULES == ("jan31", "dec31_strict")
    assert MODES == ("synthetic", "real")
