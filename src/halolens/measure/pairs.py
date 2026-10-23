"""Consecutive-lease matching on the safe unit key with an exclusion audit.

Owner: MSR. Implements `build_pairs` (AGENTS.md Section 7.3) and a gap-bound sensitivity helper.

Units are matched on `cfg["pairs"]["unit_key"]` (prop_code + unit_code, the safe key) and
cross-checked against `unit_id` (the source unit id). The site name is never used as a key; `key_comparison` reads it only to
demonstrate the collision of the unsafe key. Every consecutive pair is returned,
eligible or not; an excluded pair always carries a non-empty `exclusion_reason`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from halolens.contracts import DAYS_PER_YEAR, PAIRS_COLUMNS, PERCENT
from halolens.io.qa import SAFE_UNIT_KEY, UNSAFE_UNIT_KEY

# Exclusion reasons (several are joined with REASON_SEPARATOR when a pair fails more than one rule)
REASON_MISSING_VALUE = "missing_rent_or_date"
REASON_NON_POSITIVE_RENT = "non_positive_rent"
REASON_GAP_TOO_SHORT = "gap_too_short"
REASON_GAP_TOO_LONG = "gap_too_long"
REASON_UNIT_ID_MISMATCH = "unit_id_mismatch"
REASON_SEPARATOR = ";"

# Source columns used only by the key comparison demo (canonical tables have no site name)
SOURCE_UNIT_ID = "hUnit"
SOURCE_LEASE_START = "sLeaseFrom"

# Columns carried from the later lease of the pair (segment attributes describe the new lease)
CURRENT_LEASE_COLUMNS = ["unit_id", "prop_code", "building", "province", "beds", "is_renewal",
                         "lease_start", "sign_date", "rent_contract"]


def _annualized_log_growth(previous: pd.Series, current: pd.Series, gap_years: pd.Series) -> pd.Series:
    """ln(current / previous) / gap_years where both rents are positive and the gap is positive, else NaN."""
    valid = (previous > 0) & (current > 0) & (gap_years > 0)
    growth = pd.Series(np.nan, index=current.index, dtype=float)
    growth[valid] = np.log(current[valid] / previous[valid]) / gap_years[valid]
    return growth


def _exclusion_reasons(pairs: pd.DataFrame, min_gap: float, max_gap: float) -> pd.Series:
    """One reason string per pair; empty string when the pair is eligible."""
    rents = pairs[["rent_contract_prev", "rent_contract", "rent_net_prev", "rent_net"]]
    dates = pairs[["prev_lease_start", "lease_start"]]
    missing = rents.isna().any(axis=1) | dates.isna().any(axis=1)
    rules = {
        REASON_MISSING_VALUE: missing,
        REASON_NON_POSITIVE_RENT: (rents <= 0).any(axis=1),
        REASON_GAP_TOO_SHORT: pairs["gap_years"] <= min_gap,
        REASON_GAP_TOO_LONG: pairs["gap_years"] >= max_gap,
        REASON_UNIT_ID_MISMATCH: pairs["unit_id"] != pairs["_unit_id_prev"],
    }
    reasons = pd.Series("", index=pairs.index, dtype=object)
    for reason, failed in rules.items():
        failed = failed.fillna(False).astype(bool)
        reasons[failed] = reasons[failed].map(lambda existing: f"{existing}{REASON_SEPARATOR}{reason}"
                                              if existing else reason)
    return reasons


def build_pairs(leases: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Return a PAIRS table (contracts.PAIRS_COLUMNS) with eligible flag and exclusion_reason for every consecutive pair.

    Inputs: canonical LEASES table; merged config (uses `pairs.unit_key`, `pairs.cross_check_key`,
    `pairs.min_gap_years`, `pairs.max_gap_years`).
    Output: one row per consecutive lease pair of the same unit (n_leases − n_units rows). Leases are
    ordered by `lease_start` (then `lease_seq`) within the unit key. Segment attributes, `sign_date`
    and `year` come from the later lease. `gap_years` = days between lease starts / 365.25. Growth is
    annualized log growth, computed whenever both rents are positive and the gap is positive (so the
    sensitivity helper can re-apply other bounds); `eligible` applies the configured strict bounds.
    Assumptions: the input is not modified; no threshold is learned here (winsorizing happens downstream
    on training data only).
    """
    settings = cfg["pairs"]
    unit_key = list(settings["unit_key"])
    cross_check_key = settings["cross_check_key"]

    ordered = leases.sort_values(unit_key + ["lease_start", "lease_seq"], kind="mergesort")
    previous = ordered.groupby(unit_key, sort=False, dropna=False).shift(1)
    has_previous = ordered.groupby(unit_key, sort=False, dropna=False).cumcount() > 0

    current = ordered.loc[has_previous]
    previous = previous.loc[has_previous]

    pairs = current[CURRENT_LEASE_COLUMNS].copy()
    pairs["rent_net"] = current["rent_net_all_incentives"]
    pairs["prev_lease_start"] = previous["lease_start"]
    pairs["rent_contract_prev"] = previous["rent_contract"]
    pairs["rent_net_prev"] = previous["rent_net_all_incentives"]
    pairs["_unit_id_prev"] = previous[cross_check_key]
    pairs["year"] = pairs["lease_start"].dt.year.astype("Int64")
    pairs["gap_years"] = (pairs["lease_start"] - pairs["prev_lease_start"]).dt.days / DAYS_PER_YEAR
    pairs["loggrowth_contract"] = _annualized_log_growth(pairs["rent_contract_prev"], pairs["rent_contract"],
                                                         pairs["gap_years"])
    pairs["loggrowth_net"] = _annualized_log_growth(pairs["rent_net_prev"], pairs["rent_net"], pairs["gap_years"])
    pairs["exclusion_reason"] = _exclusion_reasons(pairs, settings["min_gap_years"], settings["max_gap_years"])
    pairs["eligible"] = (pairs["exclusion_reason"] == "").astype(bool)

    return pairs[PAIRS_COLUMNS].reset_index(drop=True)


def exclusion_summary(pairs: pd.DataFrame) -> pd.DataFrame:
    """Counts of pairs per exclusion reason (a pair failing several rules counts once per rule). Aggregates only."""
    reasons = pairs.loc[~pairs["eligible"], "exclusion_reason"].str.split(REASON_SEPARATOR).explode()
    counts = reasons.value_counts().rename_axis("exclusion_reason").rename("n_pairs").reset_index()
    eligible = pd.DataFrame({"exclusion_reason": ["(eligible)"], "n_pairs": [int(pairs["eligible"].sum())]})
    return pd.concat([eligible, counts], ignore_index=True)


def gap_sensitivity(pairs: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Re-apply alternative gap bounds to a PAIRS table and summarize. Aggregates only.

    Rows: `base` (configured bounds) and `include_six_month` (lower bound `sensitivity_min_gap_years`).
    Non-gap exclusion rules stay in force. Columns: scenario, min_gap_years, max_gap_years, n_eligible,
    median_contract_pct and median_net_pct (annualized, in percent, from the plain median of log growth).
    """
    settings = cfg["pairs"]
    scenarios = {
        "base": settings["min_gap_years"],
        "include_six_month": settings["sensitivity_min_gap_years"],
    }
    max_gap = settings["max_gap_years"]
    gap_reasons = {REASON_GAP_TOO_SHORT, REASON_GAP_TOO_LONG}
    other_reasons_ok = pairs["exclusion_reason"].str.split(REASON_SEPARATOR).apply(
        lambda reasons: all(reason in gap_reasons or reason == "" for reason in reasons))

    rows = []
    for name, min_gap in scenarios.items():
        kept = pairs[other_reasons_ok & (pairs["gap_years"] > min_gap) & (pairs["gap_years"] < max_gap)]
        rows.append({
            "scenario": name,
            "min_gap_years": min_gap,
            "max_gap_years": max_gap,
            "n_eligible": len(kept),
            "median_contract_pct": PERCENT * np.expm1(kept["loggrowth_contract"].median()),
            "median_net_pct": PERCENT * np.expm1(kept["loggrowth_net"].median()),
        })
    return pd.DataFrame(rows)


def key_comparison(raw_leases: pd.DataFrame) -> pd.DataFrame:
    """Safe (property code + unit code) vs unsafe (site name + unit code) matching key on the SOURCE lease table. Counts only.

    This is the only place the site name is read, to demonstrate the key collision. For each key:
    n_keys (distinct key values), n_units (distinct source unit ids), n_keys_with_several_units, n_leases_in_mixed_keys and
    n_cross_unit_pairs (consecutive leases by start date under that key that belong to two different source unit ids, i.e.
    pairs that would compare two different apartments).
    """
    lease_start = pd.to_datetime(raw_leases[SOURCE_LEASE_START])
    rows = []
    for name, key in (("safe: property code + unit code", SAFE_UNIT_KEY), ("unsafe: site name + unit code", UNSAFE_UNIT_KEY)):
        frame = raw_leases[key + [SOURCE_UNIT_ID]].assign(_start=lease_start)
        units_per_key = frame.groupby(key)[SOURCE_UNIT_ID].transform("nunique")
        ordered = frame.sort_values(key + ["_start"], kind="mergesort")
        previous_unit = ordered.groupby(key, sort=False)[SOURCE_UNIT_ID].shift(1)
        rows.append({
            "key": name,
            "n_keys": int(frame.groupby(key).ngroups),
            "n_units": int(frame[SOURCE_UNIT_ID].nunique()),
            "n_keys_with_several_units": int((frame.groupby(key)[SOURCE_UNIT_ID].nunique() > 1).sum()),
            "n_leases_in_mixed_keys": int((units_per_key > 1).sum()),
            "n_cross_unit_pairs": int((previous_unit.notna() & (previous_unit != ordered[SOURCE_UNIT_ID])).sum()),
        })
    return pd.DataFrame(rows)
