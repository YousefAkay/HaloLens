"""Concession→lease candidate generation and assignment.

Owner: FCT. Implements `link_concessions` (AGENTS.md Section 7.3).

The concessions table carries a unit but no lease identifier, so each concession is assigned to a lease of the same unit:
1. Candidates: leases of the same `unit_id`, signed on or before the concession's `date_from`, and not ended before it.
2. One candidate -> `unique`. No candidate -> `unresolved` (rule `no_candidate`).
3. Several candidates -> try every joint assignment of the unit's ambiguous concessions and keep the one whose
   reconstructed net rents (see `reconcile`) fit the reported rents best. Concessions whose lease is the same in every
   assignment within the tolerance of the best are `resolved_by_fit`; the others stay `unresolved`.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from halolens.contracts import LINKS_COLUMNS
from halolens.incentives.reconcile import LEASE_KEY, credit_totals, lease_term_months, reconstruct_net_rent

RULE_SINGLE = "single_candidate"
RULE_NONE = "no_candidate"
RULE_FIT = "best_fit"
RULE_TIED = "tied_fit"
RULE_TOO_MANY = "too_many_combinations"
STATUS_UNIQUE, STATUS_FIT, STATUS_UNRESOLVED = "unique", "resolved_by_fit", "unresolved"


def _candidates(concessions: pd.DataFrame, leases: pd.DataFrame) -> pd.DataFrame:
    """One row per (concession, candidate lease): same unit, signed on/before date_from, lease_end on/after date_from."""
    pairs = concessions[["concession_id", "unit_id", "date_from"]].merge(
        leases[["unit_id", "lease_start", "lease_end", "sign_date"]], on="unit_id", how="inner")
    keep = (pairs["sign_date"] <= pairs["date_from"]) & (pairs["lease_end"] >= pairs["date_from"])
    return pairs.loc[keep, ["concession_id", "unit_id", "lease_start"]]


def _fit_error(unit_leases: pd.DataFrame, fixed_credit: pd.Series, assignment: dict[int, pd.Timestamp],
               totals: pd.Series) -> float:
    """Sum over a unit's leases of |reconstructed - reported net rent| for one joint assignment of ambiguous concessions."""
    credit = fixed_credit.copy()
    for concession_id, lease_start in assignment.items():
        credit[lease_start] = credit.get(lease_start, 0.0) + totals[concession_id]
    reconstructed = unit_leases["rent_contract"].to_numpy() - credit.reindex(unit_leases["lease_start"]).fillna(0.0).to_numpy() / unit_leases["term_months"].to_numpy()
    return float(np.abs(reconstructed - unit_leases["rent_net_all_incentives"].to_numpy()).sum())


def _resolve_unit(unit_leases: pd.DataFrame, fixed_credit: pd.Series, ambiguous: pd.DataFrame, totals: pd.Series,
                  cfg: dict) -> dict[int, tuple[pd.Timestamp | None, str, str]]:
    """Assign one unit's ambiguous concessions jointly. Returns {concession_id: (lease_start or None, status, rule)}."""
    choices = {cid: sorted(rows["lease_start"]) for cid, rows in ambiguous.groupby("concession_id")}
    ids = sorted(choices)
    combinations = int(np.prod([len(choices[cid]) for cid in ids]))
    if combinations > cfg["linking"]["max_combinations"]:
        return {cid: (None, STATUS_UNRESOLVED, RULE_TOO_MANY) for cid in ids}

    scored = []
    for combo in itertools.product(*(choices[cid] for cid in ids)):
        assignment = dict(zip(ids, combo))
        scored.append((_fit_error(unit_leases, fixed_credit, assignment, totals), assignment))
    best_error = min(error for error, _ in scored)
    tied = [assignment for error, assignment in scored if error <= best_error + cfg["linking"]["recon_tolerance_dollars"]]
    outcome = {}
    for cid in ids:
        leases_chosen = {assignment[cid] for assignment in tied}
        if len(leases_chosen) == 1:
            outcome[cid] = (next(iter(leases_chosen)), STATUS_FIT, RULE_FIT)
        else:
            outcome[cid] = (None, STATUS_UNRESOLVED, RULE_TIED)
    return outcome


def link_concessions(concessions: pd.DataFrame, leases: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Return a LINKS table: candidates = same unit, signed on/before date_from, still active; resolve ties by reconciliation fit.

    Inputs: canonical CONCESSIONS and LEASES tables, merged config (`linking.*`). Output: one row per concession with
    contracts.LINKS_COLUMNS. `lease_start` identifies the assigned lease together with `unit_id` (NaT if unresolved);
    `n_candidates` counts the leases that passed the candidate rule; `rule` says how the status was reached;
    `recon_error` is the absolute reconstruction error (dollars per month) of the assigned lease once every link is in
    place (NaN if unresolved). Assumes (unit_id, lease_start) identifies a lease. Amounts are never multiplied here:
    credit totals come from `reconcile.credit_totals` (lump once, monthly x months).
    """
    candidates = _candidates(concessions, leases)
    n_candidates = candidates.groupby("concession_id").size()
    links = concessions[["concession_id", "unit_id"]].copy()
    links["n_candidates"] = links["concession_id"].map(n_candidates).fillna(0).astype(int)
    links["lease_start"] = pd.Series(pd.NaT, index=links.index, dtype="datetime64[ns]")
    links["rule"], links["status"] = RULE_NONE, STATUS_UNRESOLVED

    single = links["n_candidates"] == 1
    only = candidates[candidates["concession_id"].isin(links.loc[single, "concession_id"])].set_index("concession_id")
    links.loc[single, "lease_start"] = links.loc[single, "concession_id"].map(only["lease_start"]).to_numpy()
    links.loc[single, ["rule", "status"]] = [RULE_SINGLE, STATUS_UNIQUE]

    ambiguous_ids = links.loc[links["n_candidates"] > 1, "concession_id"]
    if len(ambiguous_ids):
        totals = credit_totals(concessions).set_index("concession_id")["total"]
        sized = leases.assign(term_months=lease_term_months(leases))
        fixed = candidates[candidates["concession_id"].isin(links.loc[single, "concession_id"])]
        fixed_credit = fixed.assign(total=fixed["concession_id"].map(totals)).groupby(LEASE_KEY, as_index=False)["total"].sum()
        outcome = {}
        ambiguous = candidates[candidates["concession_id"].isin(ambiguous_ids)]
        for unit_id, rows in ambiguous.groupby("unit_id"):
            unit_leases = sized[sized["unit_id"] == unit_id].sort_values("lease_start")
            unit_fixed = fixed_credit[fixed_credit["unit_id"] == unit_id].set_index("lease_start")["total"]
            outcome.update(_resolve_unit(unit_leases, unit_fixed, rows, totals, cfg))
        for concession_id, (lease_start, status, rule) in outcome.items():
            row = links["concession_id"] == concession_id
            links.loc[row, "lease_start"] = lease_start if lease_start is not None else pd.NaT
            links.loc[row, ["rule", "status"]] = [rule, status]

    rebuilt = reconstruct_net_rent(leases, concessions, links)
    error = rebuilt.assign(recon_error=rebuilt["recon_error"].abs()).set_index(LEASE_KEY)["recon_error"]
    keyed = pd.MultiIndex.from_frame(links[LEASE_KEY])
    links["recon_error"] = error.reindex(keyed).to_numpy()
    links.loc[links["lease_start"].isna(), "recon_error"] = np.nan
    return links[LINKS_COLUMNS].sort_values("concession_id").reset_index(drop=True)
