"""Québec (TAL) vs Ontario (guideline) applicability matrix and scenarios.

Implements `applicability_matrix`, plus `reference_lines`, `exemption_evidence` and
`renewals_vs_reference` for notebook section 06.

Québec buildings are under the TAL, Ontario buildings under Ontario's Residential Tenancies Act. A province's rule is only
ever compared with that province's leases. The matrix is a reading of public rules used to design scenarios
(newer Québec buildings: possible lease clause F; Ontario new-build: possible post-November-15-2018 exemption). It is never a
legal determination. Reference percentages come from `data/public/sources.csv` with their release dates.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from halolens.config import cutoff_for, external_cutoff_for
from halolens.contracts import PERCENT

MATRIX_COLUMNS = [
    "building", "province", "lease_type", "regime", "rule", "scenario",
    "central", "alternative", "reference_metric_central", "reference_metric_alternative",
    "binding_central", "binding_alternative", "first_lease_year", "latest_phase_first_lease_year",
]
REFERENCE_COLUMNS = [
    "year", "province", "metric", "reference_pct", "release_date", "url", "known_by_info_date", "known_by_strict_cutoff",
]
COMPARISON_COLUMNS = [
    "year", "province", "n_pairs", "mean_contract_pct", "reference_pct", "gap_pp", "release_date",
    "known_by_info_date", "known_by_strict_cutoff",
]
EVIDENCE_COLUMNS = ["year", "n_renewals", "n_above_reference", "share_above_reference", "reference_pct"]
EXEMPTION_SCENARIO = "ontario_post_2018_exemption"
LEASE_TYPES = ("renewal", "turnover")
NO_SCENARIO = "none"
CENTRAL_ONLY_TEXT = "Pas de scénario réglementaire distinct."


def _regime_name(province: str, cfg: dict) -> str:
    settings = cfg["regulation"]
    return settings["quebec_regime"] if province == "QC" else settings["ontario_regime"]


def _first_lease_years(leases: pd.DataFrame) -> pd.DataFrame:
    """Per building: first lease-start year in the extract, and the latest first year among its phases (prop codes)."""
    first_by_phase = leases.groupby(["building", "prop_code"], observed=True)["lease_start"].min().dt.year
    by_building = first_by_phase.groupby(level="building")
    return pd.DataFrame({"first_lease_year": by_building.min(),
                         "latest_phase_first_lease_year": by_building.max()}).reset_index()


def applicability_matrix(cfg: dict, leases: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return one row per building x lease type with regime, evidence and scenario flags. Never a legal determination.

    Inputs: merged config (`regulation.buildings`, `regulation.regimes`, `regulation.scenarios`); optional canonical
    LEASES, used only to add evidence columns (first lease-start year per building and the latest first year among
    its phases; aggregates only). Output columns MATRIX_COLUMNS. `reference_metric_*` names the public series that is
    the relevant benchmark under each scenario ("" = none); `binding_*` tells whether it is a legal ceiling.
    Scenarios change renewals only: turnovers are never capped by the TAL percentage or the Ontario guideline.
    """
    settings = cfg["regulation"]
    rows = []
    for entry in settings["buildings"]:
        province = entry["province"]
        scenario_name = entry.get("scenario", NO_SCENARIO)
        for lease_type in LEASE_TYPES:
            regime = settings["regimes"][province][lease_type]
            metric, binding = regime["reference_metric"], bool(regime["binding"])
            row = {
                "building": entry["building"], "province": province, "lease_type": lease_type,
                "regime": _regime_name(province, cfg), "rule": regime["rule"], "scenario": NO_SCENARIO,
                "central": CENTRAL_ONLY_TEXT, "alternative": CENTRAL_ONLY_TEXT,
                "reference_metric_central": metric, "reference_metric_alternative": metric,
                "binding_central": binding, "binding_alternative": binding,
            }
            if scenario_name != NO_SCENARIO and lease_type == "renewal":
                scenario = settings["scenarios"][scenario_name]
                row.update(scenario=scenario_name, central=scenario["central"], alternative=scenario["alternative"])
                for case in ("central", "alternative"):
                    applies = bool(scenario[f"{case}_reference"])
                    row[f"reference_metric_{case}"] = metric if applies else ""
                    row[f"binding_{case}"] = binding and applies
            rows.append(row)
    matrix = pd.DataFrame(rows)
    if leases is not None:
        matrix = matrix.merge(_first_lease_years(leases), on="building", how="left")
    else:
        matrix["first_lease_year"] = pd.NA
        matrix["latest_phase_first_lease_year"] = pd.NA
    return matrix[MATRIX_COLUMNS]


def reference_lines(external: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Regulatory reference percentage per year and province from the EXTERNAL table.

    Uses `regulation.reference_metrics` (QC: TAL reference %, ON: guideline). `year` is the calendar year the
    percentage applies to (its reference period). `known_by_info_date` is True when `release_date` <=
    `external_cutoff_for(year)` (January 31 of that year): the value was public in time for that
    year's forecast. `known_by_strict_cutoff` applies the Dec-31-of-y-1 cutoff instead (sensitivity only).
    Output columns REFERENCE_COLUMNS, sorted by province and year.
    """
    metrics = cfg["regulation"]["reference_metrics"]
    parts = []
    for province, metric in metrics.items():
        rows = external[(external["metric"] == metric) & (external["geography"] == province)]
        parts.append(rows.assign(province=province))
    lines = pd.concat(parts) if parts else external.iloc[:0].assign(province="")
    lines = lines.assign(year=lines["ref_period_start"].dt.year.astype(int), reference_pct=lines["value"])
    info_dates = lines["year"].map(lambda year: external_cutoff_for(int(year), cfg))
    strict_dates = lines["year"].map(lambda year: cutoff_for(int(year), cfg))
    lines["known_by_info_date"] = lines["release_date"] <= info_dates
    lines["known_by_strict_cutoff"] = lines["release_date"] <= strict_dates
    return lines[REFERENCE_COLUMNS].sort_values(["province", "year"]).reset_index(drop=True)


def renewals_vs_reference(split: pd.DataFrame, references: pd.DataFrame) -> pd.DataFrame:
    """Renewal contractual growth next to the same province's reference percentage for the same year.

    Inputs: `measure.renewals.split_summary` output and `reference_lines` output. Only renewal rows are kept and
    the join is on year AND province, so a province's rule is never applied to the other province.
    `gap_pp` = renewal mean contractual growth (%) - reference (%): how far observed renewals sit from the benchmark.
    Output columns COMPARISON_COLUMNS.
    """
    renewals = split[split["is_renewal"].astype(bool)][["year", "province", "n_pairs", "mean_contract_pct"]]
    merged = renewals.merge(references, on=["year", "province"], how="inner")
    merged["gap_pp"] = merged["mean_contract_pct"] - merged["reference_pct"]
    return merged[COMPARISON_COLUMNS].sort_values(["province", "year"]).reset_index(drop=True)


def exemption_evidence(pairs: pd.DataFrame, references: pd.DataFrame, cfg: dict, years: list[int]) -> pd.DataFrame:
    """Per year: how many renewals of the buildings in the Ontario post-2018 exemption scenario rose above the guideline.

    Inputs: PAIRS (eligible renewal rows of buildings whose `regulation.buildings` scenario is
    `ontario_post_2018_exemption` are used); `reference_lines` output; config; the years to report (every year gets a
    row, with zero renewals when none was observed). A renewal is above the guideline when its 12-month contractual
    increase (rent_contract / rent_contract_prev - 1, in %) exceeds the guideline by more than
    `regulation.exemption_evidence.above_reference_tolerance_pp`. Output columns EVIDENCE_COLUMNS (aggregates only).
    Renewals well above the guideline are consistent with an exemption, not proof of it.
    """
    settings = cfg["regulation"]
    tolerance = settings["exemption_evidence"]["above_reference_tolerance_pp"]
    buildings = [entry["building"] for entry in settings["buildings"] if entry.get("scenario") == EXEMPTION_SCENARIO]
    provinces = {entry["province"] for entry in settings["buildings"] if entry.get("scenario") == EXEMPTION_SCENARIO}
    renewals = pairs[pairs["eligible"] & pairs["is_renewal"].astype(bool) & pairs["building"].isin(buildings)]
    increase_pct = PERCENT * (renewals["rent_contract"] / renewals["rent_contract_prev"] - 1)
    guideline = references[references["province"].isin(provinces)].set_index("year")["reference_pct"]
    rows = []
    for year in years:
        in_year = renewals["year"] == year
        reference = float(guideline.get(year, np.nan))
        above = int((increase_pct[in_year] > reference + tolerance).sum()) if not np.isnan(reference) else 0
        count = int(in_year.sum())
        rows.append({"year": year, "n_renewals": count, "n_above_reference": above,
                     "share_above_reference": above / count if count else np.nan, "reference_pct": reference})
    return pd.DataFrame(rows, columns=EVIDENCE_COLUMNS)
