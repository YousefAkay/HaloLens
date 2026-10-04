"""Tests for the renewal/turnover split (measure.renewals) and the QC/ON regulation matrix (market.regulation).

Owner: MSR. Fixtures: hand-made pairs and reference rows, the committed synthetic data and the committed public
sources. Never CRM data.
"""

from __future__ import annotations

import copy
import math

import numpy as np
import pandas as pd
import pytest

from leaselens.config import cutoff_for, external_cutoff_for, load_config
from leaselens.contracts import PAIRS_COLUMNS, PERCENT
from leaselens.market.registry import load_external
from leaselens.market.regulation import (COMPARISON_COLUMNS, EVIDENCE_COLUMNS, MATRIX_COLUMNS, REFERENCE_COLUMNS,
                                         applicability_matrix, exemption_evidence, reference_lines,
                                         renewals_vs_reference)
from leaselens.measure.pairs import build_pairs
from leaselens.measure.renewals import NOTE_THIN_CELL, SPLIT_COLUMNS, split_summary

YEAR = 2024
RENEWAL_GROWTH = 0.03
TURNOVER_GROWTH = 0.08
NET_DISCOUNT = 0.01
BASE_RENT = 1000.0
TARGET_YEAR = 2026
TAL_TARGET_RELEASE = pd.Timestamp("2026-01-19")


def pair(unit: str, province: str, renewal: bool, growth: float, year: int = YEAR) -> dict:
    """One eligible annual pair with the given contractual log growth and a fixed net discount."""
    start = pd.Timestamp(f"{year}-07-01")
    return {
        "unit_id": unit, "prop_code": "aaa", "building": "Test", "province": province, "beds": 1,
        "is_renewal": renewal, "prev_lease_start": start - pd.DateOffset(years=1), "lease_start": start,
        "sign_date": start - pd.Timedelta(days=60), "year": year, "gap_years": 1.0,
        "rent_contract_prev": BASE_RENT, "rent_contract": BASE_RENT * math.exp(growth),
        "rent_net_prev": BASE_RENT, "rent_net": BASE_RENT * math.exp(growth - NET_DISCOUNT),
        "loggrowth_contract": growth, "loggrowth_net": growth - NET_DISCOUNT, "eligible": True, "exclusion_reason": "",
    }


def pairs_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)[PAIRS_COLUMNS]


@pytest.fixture
def no_clip_cfg(cfg) -> dict:
    """Config whose winsorization keeps every value (hand-made growth must come out exactly)."""
    adjusted = copy.deepcopy(cfg)
    adjusted["winsorize"]["lower_quantile"] = 0.0
    adjusted["winsorize"]["upper_quantile"] = 1.0
    return adjusted


@pytest.fixture(scope="module")
def real_cfg() -> dict:
    """Config with the real building list (regulation keys do not depend on the data mode; no CRM file is read)."""
    return load_config(mode="real")


@pytest.fixture(scope="module")
def public_external(real_cfg) -> pd.DataFrame:
    """The committed, verified public sources (no CRM content)."""
    settings = real_cfg["data"]
    return load_external(f"{real_cfg['_root']}/{settings['public_dir']}/{real_cfg['external']['sources_file']}")


def test_split_separates_renewals_and_turnovers_per_province(no_clip_cfg):
    count = no_clip_cfg["renewals"]["min_pairs_per_cell"]
    rows = [pair(f"r{i}", "QC", True, RENEWAL_GROWTH) for i in range(count)]
    rows += [pair(f"t{i}", "QC", False, TURNOVER_GROWTH) for i in range(count)]
    rows += [pair(f"o{i}", "ON", False, TURNOVER_GROWTH) for i in range(count)]
    split = split_summary(pairs_frame(rows), no_clip_cfg)
    assert list(split.columns) == SPLIT_COLUMNS
    split = split.set_index(["province", "lease_type"])
    assert split.loc[("QC", "renewal"), "mean_contract_pct"] == pytest.approx(PERCENT * math.expm1(RENEWAL_GROWTH))
    assert split.loc[("QC", "turnover"), "mean_contract_pct"] == pytest.approx(PERCENT * math.expm1(TURNOVER_GROWTH))
    assert split.loc[("QC", "renewal"), "incentive_pp"] == pytest.approx(-PERCENT * NET_DISCOUNT)
    assert ("ON", "renewal") not in split.index      # no Ontario renewals in the input: no row invented
    assert set(split["n_pairs"]) == {count}


def test_thin_cell_keeps_count_but_hides_growth(no_clip_cfg):
    count = no_clip_cfg["renewals"]["min_pairs_per_cell"] - 1
    rows = [pair(f"r{i}", "QC", True, RENEWAL_GROWTH) for i in range(count)]
    split = split_summary(pairs_frame(rows), no_clip_cfg)
    assert split.loc[0, "n_pairs"] == count
    assert np.isnan(split.loc[0, "mean_net_pct"]) and split.loc[0, "note"] == NOTE_THIN_CELL


def test_ineligible_pairs_are_ignored(no_clip_cfg):
    count = no_clip_cfg["renewals"]["min_pairs_per_cell"]
    rows = [pair(f"r{i}", "QC", True, RENEWAL_GROWTH) for i in range(count)]
    rows.append({**pair("bad", "QC", True, TURNOVER_GROWTH), "eligible": False, "exclusion_reason": "gap_too_long"})
    split = split_summary(pairs_frame(rows), no_clip_cfg)
    assert split.loc[0, "n_pairs"] == count
    assert split.loc[0, "mean_contract_pct"] == pytest.approx(PERCENT * math.expm1(RENEWAL_GROWTH))


def test_split_runs_on_synthetic(tables, cfg):
    pairs = build_pairs(tables.leases, cfg)
    split = split_summary(pairs, cfg)
    assert list(split.columns) == SPLIT_COLUMNS
    assert split["n_pairs"].sum() == int(pairs["eligible"].sum())
    assert set(split["province"]) <= {"QC", "ON"}


def test_matrix_covers_every_building_and_lease_type(real_cfg):
    matrix = applicability_matrix(real_cfg)
    assert list(matrix.columns) == MATRIX_COLUMNS
    buildings = [entry["building"] for entry in real_cfg["regulation"]["buildings"]]
    assert len(matrix) == 2 * len(buildings)
    assert set(matrix.groupby("building")["lease_type"].apply(frozenset)) == {frozenset({"renewal", "turnover"})}


def test_matrix_never_crosses_provinces(real_cfg):
    matrix = applicability_matrix(real_cfg)
    settings = real_cfg["regulation"]
    for case in ("central", "alternative"):
        used = matrix[matrix[f"reference_metric_{case}"] != ""]
        assert (used[f"reference_metric_{case}"] == used["province"].map(settings["reference_metrics"])).all()
    assert set(matrix.loc[matrix["province"] == "ON", "regime"]) == {settings["ontario_regime"]}
    assert set(matrix.loc[matrix["province"] == "QC", "regime"]) == {settings["quebec_regime"]}


def test_turnovers_are_never_capped(real_cfg):
    turnovers = applicability_matrix(real_cfg).query("lease_type == 'turnover'")
    assert not turnovers[["binding_central", "binding_alternative"]].any().any()
    assert (turnovers["scenario"] == "none").all()


def test_ontario_exemption_scenario_matches_forecast_levers(real_cfg):
    """Central = guideline does not bind (exemption plausible); alternative = guideline binds (AGENTS.md 9.4)."""
    ontario = applicability_matrix(real_cfg).query("province == 'ON' and lease_type == 'renewal'")
    assert len(ontario) == 1
    row = ontario.iloc[0]
    assert row["scenario"] == "ontario_post_2018_exemption"
    applies = [bool(row["binding_central"]), bool(row["binding_alternative"])]
    assert applies == real_cfg["scenarios"]["met_guideline_applies"]


def test_quebec_reference_is_never_binding(real_cfg):
    quebec = applicability_matrix(real_cfg).query("province == 'QC'")
    assert not quebec[["binding_central", "binding_alternative"]].any().any()


def test_matrix_evidence_from_leases_is_per_building(tables, cfg):
    matrix = applicability_matrix(cfg, tables.leases)
    known = matrix.dropna(subset=["first_lease_year"])
    assert (known["first_lease_year"] <= known["latest_phase_first_lease_year"]).all()


def test_reference_lines_use_january_31_information_date(real_cfg, public_external):
    lines = reference_lines(public_external, real_cfg)
    assert list(lines.columns) == REFERENCE_COLUMNS
    assert set(lines["province"]) == {"QC", "ON"}
    assert (lines["metric"] == lines["province"].map(real_cfg["regulation"]["reference_metrics"])).all()
    info_dates = lines["year"].map(lambda year: external_cutoff_for(year, real_cfg))
    strict_dates = lines["year"].map(lambda year: cutoff_for(year, real_cfg))
    assert (lines["known_by_info_date"] == (lines["release_date"] <= info_dates)).all()
    assert (lines["known_by_strict_cutoff"] == (lines["release_date"] <= strict_dates)).all()


def test_tal_2026_is_known_for_the_2026_forecast_but_not_under_strict_cutoff(real_cfg, public_external):
    lines = reference_lines(public_external, real_cfg).set_index(["province", "year"])
    tal_2026 = lines.loc[("QC", TARGET_YEAR)]
    assert tal_2026["release_date"] == TAL_TARGET_RELEASE
    assert bool(tal_2026["known_by_info_date"]) and not bool(tal_2026["known_by_strict_cutoff"])


def test_renewals_vs_reference_joins_same_province_only(no_clip_cfg):
    count = no_clip_cfg["renewals"]["min_pairs_per_cell"]
    rows = [pair(f"r{i}", "QC", True, RENEWAL_GROWTH) for i in range(count)]
    rows += [pair(f"t{i}", "QC", False, TURNOVER_GROWTH) for i in range(count)]
    split = split_summary(pairs_frame(rows), no_clip_cfg)
    reference_pct = {"QC": 4.0, "ON": 2.5}
    references = pd.DataFrame({
        "year": [YEAR, YEAR], "province": ["QC", "ON"],
        "metric": ["tal_renewal_reference_pct", "ontario_guideline_pct"],
        "reference_pct": [reference_pct["QC"], reference_pct["ON"]],
        "release_date": pd.to_datetime([f"{YEAR}-01-15", f"{YEAR - 1}-08-31"]), "url": ["", ""],
        "known_by_info_date": [True, True], "known_by_strict_cutoff": [False, True]})
    comparison = renewals_vs_reference(split, references)
    assert list(comparison.columns) == COMPARISON_COLUMNS
    assert list(comparison["province"]) == ["QC"]     # no Ontario renewals: the guideline is not applied to Québec
    expected_gap = PERCENT * math.expm1(RENEWAL_GROWTH) - reference_pct["QC"]
    assert comparison.loc[0, "gap_pp"] == pytest.approx(expected_gap)


def met_renewal(unit: str, year: int, increase_pct: float) -> dict:
    """One eligible renewal pair of the Ontario new-build with the given 12-month contractual increase."""
    row = pair(unit, "ON", True, math.log1p(increase_pct / PERCENT), year)
    return {**row, "building": "the Ontario new-build"}


def test_exemption_evidence_counts_renewals_above_guideline(real_cfg):
    guideline = 2.5
    years = [YEAR - 1, YEAR]
    rows = [met_renewal("a", YEAR, guideline), met_renewal("b", YEAR, guideline + 1.0),
            met_renewal("c", YEAR, guideline + 3.0)]
    rows.append({**pair("q", "QC", True, 0.2), "building": "Building"})   # Québec renewal: never counted
    references = pd.DataFrame({"year": years, "province": ["ON", "ON"], "reference_pct": [guideline, guideline]})
    evidence = exemption_evidence(pairs_frame(rows), references, real_cfg, years).set_index("year")
    assert list(evidence.reset_index().columns) == EVIDENCE_COLUMNS
    assert evidence.loc[YEAR - 1, "n_renewals"] == 0 and np.isnan(evidence.loc[YEAR - 1, "share_above_reference"])
    assert evidence.loc[YEAR, "n_renewals"] == 3              # a renewal exactly at the guideline is not above it
    assert evidence.loc[YEAR, "n_above_reference"] == 2
    assert evidence.loc[YEAR, "share_above_reference"] == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# measure.labels (French dates in notebook text) and the templated config text
# ---------------------------------------------------------------------------
def test_french_dates_from_config():
    from leaselens.measure.labels import french_date, french_month, french_month_day, french_month_year
    assert french_date("2018-11-15") == "15 novembre 2018"
    assert french_date("2026-01-01") == "1er janvier 2026"
    assert french_date("2026-01-19", with_year=False) == "19 janvier"
    assert french_month_day("12-31") == "31 décembre"
    assert french_month_day("02-29") == "29 février"
    assert french_month("2025-10-01") == "octobre"
    assert french_month_year("2023-05") == "mai 2023"


def test_post_cutoff_note_template_fills_every_placeholder():
    cfg = load_config(mode="synthetic")
    note = cfg["regulation"]["post_cutoff_note"].format(
        target_year=TARGET_YEAR, tal_release="a", info_date="b", method_change="c", strict_cutoff="d",
        strict_known="e")
    assert "{" not in note and str(TARGET_YEAR) in note


def test_exemption_evidence_has_dated_source_fields():
    settings = load_config(mode="synthetic")["regulation"]["exemption_evidence"]
    for key in ("occupancy_source_label", "occupancy_source_date", "occupancy_start_month", "building_units",
                "building_address", "law_citation", "law_url", "occupancy_url"):
        assert settings[key] not in ("", None), key
    assert pd.Timestamp(settings["occupancy_start_month"]) <= pd.Timestamp(settings["occupancy_source_date"])
