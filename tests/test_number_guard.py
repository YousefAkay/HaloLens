"""Tests for app/number_guard.py. Owner: INT.

Uses a small invented aggregates dict; no CRM data and no results.
"""

from __future__ import annotations

import pytest

from app.number_guard import (
    UngroundedNumberError,
    check_grounded,
    extract_numbers,
    json_values,
    ungrounded_numbers,
)

AGGREGATES = {
    "as_of": "2025-12-31",
    "headline": {"net_pct": 3.47, "contract_pct": 4.1},
    "backtest": [{"year": 2024, "error_pp_net": -0.8}],
    "coverage": {"eligible_pairs": 1234, "units_with_two_leases": 567},
    "scenario": {"low_pct": 2.1, "high_pct": 5.9},
}


def test_value_grounded_at_written_precision():
    assert ungrounded_numbers("La hausse nette est de 3,5 %.", AGGREGATES) == []


def test_value_at_wrong_precision_is_rejected():
    # 3.47 rounds to 3.4 at one decimal, so "3,9" is not supported
    assert ungrounded_numbers("La hausse est de 3,9 %.", AGGREGATES) == ["3,9"]


def test_invented_number_is_reported():
    assert ungrounded_numbers("Une hausse de 7,2 % est attendue.", AGGREGATES) == ["7,2"]


def test_thousands_separator_grounds_integer():
    assert ungrounded_numbers("Il y a 1 234 baux éligibles.", AGGREGATES) == []


def test_negative_numbers_use_the_sign():
    assert ungrounded_numbers("L'erreur est de −0,8 point.", AGGREGATES) == []
    # "+" is not a sign in the pattern, so the text reads as +0.8, which the JSON does not contain
    assert ungrounded_numbers("L'erreur est de +0,8 point.", AGGREGATES) == ["0,8"]


def test_dates_in_json_strings_ground_their_digits():
    assert ungrounded_numbers("Données au 31 décembre 2025 ; erreur en 2024.", AGGREGATES) == []


def test_target_year_absent_from_json_is_rejected():
    assert ungrounded_numbers("Cible 2026.", AGGREGATES) == ["2026"]


def test_labels_such_as_q1_are_not_numbers():
    assert [number.text for number in extract_numbers("Q1 2025")] == ["2025"]


def test_booleans_do_not_ground_numbers():
    assert json_values({"flag": True, "count": 0}) == [0.0]
    assert ungrounded_numbers("Soit 1 cas.", {"flag": True}) == ["1"]


def test_percent_stored_as_fraction_is_rejected():
    # Convention: percentages are stored in percent units (3.47), not fractions (0.0347)
    assert ungrounded_numbers("Hausse de 3,5 %.", {"net_pct": 0.035}) == ["3,5"]


def test_text_without_numbers_passes():
    assert ungrounded_numbers("Aucun chiffre ici.", AGGREGATES) == []


def test_check_grounded_raises_with_offending_numbers():
    with pytest.raises(UngroundedNumberError, match="7,2") as error:
        check_grounded("Hausse de 7,2 % en 2026.", AGGREGATES)
    assert error.value.numbers == ["7,2", "2026"]


# --- section citations and long floats (Q-01) ---------------------------------------------------------------------
def test_section_citations_are_not_numbers():
    assert ungrounded_numbers("Voir §07, §11a et § 10.", {}) == []


def test_a_real_ungrounded_number_next_to_a_citation_is_still_rejected():
    assert ungrounded_numbers("Voir §07 : 12,5 % de hausse.", {}) == ["12,5"]


def test_numbers_with_too_many_decimals_are_rejected_even_if_present():
    assert ungrounded_numbers("3.535312230641093", {"x": 3.535312230641093}) != []
    assert ungrounded_numbers("3.54", {"x": 3.535312230641093}) == []
