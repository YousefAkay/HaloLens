"""Reconstruction of net rent from concession records.

Owner: FCT. Implements `reconstruct_net_rent` (AGENTS.md Section 7.3) and aggregate summaries for notebook section 05.

Working hypothesis, checked against the data rather than assumed: for a lease with monthly contract rent R and term T months,
    rent_net_all_incentives = R - (lump credits + sum of monthly credit x months) / T
where lump credits (PromoPay) count once and every other charge code is a monthly credit repeated `months` times.
Amounts are never multiplied by anything else, and a lump credit is never multiplied by its `months` value.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from leaselens.contracts import ACCESSORY_CHARGE_CODES, DAYS_PER_YEAR, MONTHS_PER_YEAR, PERCENT

LEASE_KEY = ["unit_id", "lease_start"]
RECONSTRUCTION_COLUMNS = ["unit_id", "lease_start", "rent_contract", "rent_net_reported", "term_months",
                          "n_concessions", "lump_credit_total", "monthly_credit_total", "rent_net_reconstructed",
                          "recon_error"]


def lease_term_months(leases: pd.DataFrame) -> pd.Series:
    """Whole months between lease start and end (inclusive of the last day), at least 1. Not `term_months_daycount`."""
    days = (leases["lease_end"] - leases["lease_start"]).dt.days + 1
    return np.round(days / (DAYS_PER_YEAR / MONTHS_PER_YEAR)).clip(lower=1)


def credit_totals(concessions: pd.DataFrame, lump_multiplies_months: bool = False) -> pd.DataFrame:
    """Total credit per concession row: lump credits once, monthly credits x months.

    Returns columns concession_id, kind ("lump" or "monthly") and total. `lump_multiplies_months=True` is the
    rejected alternative (lump x months) kept only so section 05 can show why it is wrong. Missing `months` on a
    monthly credit counts as 0 months.
    """
    months = concessions["months"].fillna(0)
    is_lump = concessions["credit_kind"] == "lump"
    total = np.where(is_lump, concessions["credit_amount"] * (months if lump_multiplies_months else 1),
                     concessions["credit_amount"] * months)
    return pd.DataFrame({"concession_id": concessions["concession_id"].to_numpy(),
                         "kind": np.where(is_lump, "lump", "monthly"), "total": total})


def reconstruct_net_rent(leases: pd.DataFrame, concessions: pd.DataFrame, links: pd.DataFrame,
                         lump_multiplies_months: bool = False,
                         exclude_codes: frozenset[str] = frozenset()) -> pd.DataFrame:
    """Return per lease the reconstructed net rent (lump credits once, monthly credits x months, spread over the term) and the reconciliation error.

    One row per lease (key: unit_id + lease_start). Only concessions linked with a lease_start (status unique or
    resolved_by_fit) count; unresolved ones are ignored. `recon_error` = reconstructed minus reported net rent in
    dollars per month, so a negative value means the records explain more discount than the reported rent shows.
    A lease without linked concessions is reconstructed as its contract rent.
    Optional switches serve section 05 only: `lump_multiplies_months` (rejected hypothesis) and `exclude_codes`
    (for example accessory codes, to test whether sRentEffective includes them).
    """
    linked = links.loc[links["lease_start"].notna(), ["concession_id", "unit_id", "lease_start"]]
    rows = concessions[~concessions["charge_code"].isin(exclude_codes)]
    credits = credit_totals(rows, lump_multiplies_months).merge(linked, on="concession_id", how="inner")
    per_lease = credits.pivot_table(index=LEASE_KEY, columns="kind", values="total", aggfunc="sum", fill_value=0.0)
    per_lease = per_lease.reindex(columns=["lump", "monthly"], fill_value=0.0)
    per_lease["n_concessions"] = credits.groupby(LEASE_KEY).size()
    per_lease = per_lease.rename(columns={"lump": "lump_credit_total", "monthly": "monthly_credit_total"})

    result = leases[LEASE_KEY + ["rent_contract", "rent_net_all_incentives"]].rename(
        columns={"rent_net_all_incentives": "rent_net_reported"})
    result["term_months"] = lease_term_months(leases).to_numpy()
    result = result.merge(per_lease.reset_index(), on=LEASE_KEY, how="left")
    result[["lump_credit_total", "monthly_credit_total"]] = result[["lump_credit_total", "monthly_credit_total"]].fillna(0.0)
    result["n_concessions"] = result["n_concessions"].fillna(0).astype(int)
    credit = result["lump_credit_total"] + result["monthly_credit_total"]
    result["rent_net_reconstructed"] = result["rent_contract"] - credit / result["term_months"]
    result["recon_error"] = result["rent_net_reconstructed"] - result["rent_net_reported"]
    return result[RECONSTRUCTION_COLUMNS].reset_index(drop=True)


def reconciliation_rate(reconstruction: pd.DataFrame, cfg: dict, only_discounted: bool = False) -> float:
    """Share of leases whose reconstruction error is within `linking.recon_tolerance_dollars` (NaN if no leases).

    `only_discounted=True` restricts to leases whose reported net rent is below the contract rent, which is the
    population where the concession records have something to explain.
    """
    rows = reconstruction
    if only_discounted:
        rows = rows[rows["rent_net_reported"] < rows["rent_contract"]]
    if rows.empty:
        return float("nan")
    return float((rows["recon_error"].abs() <= cfg["linking"]["recon_tolerance_dollars"]).mean())


def reconciliation_by_year(reconstruction: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Leases, discounted leases, reconciliation rates and mean absolute error (dollars) by lease-start year. Aggregates only."""
    tolerance = cfg["linking"]["recon_tolerance_dollars"]
    frame = reconstruction.assign(year=reconstruction["lease_start"].dt.year,
                                  discounted=reconstruction["rent_net_reported"] < reconstruction["rent_contract"],
                                  reconciled=reconstruction["recon_error"].abs() <= tolerance)
    rows = []
    for year, group in frame.groupby("year"):
        discounted = group[group["discounted"]]
        rows.append({"year": int(year), "n_leases": len(group), "n_discounted": len(discounted),
                     "rate_all": group["reconciled"].mean(),
                     "rate_discounted": discounted["reconciled"].mean() if len(discounted) else np.nan,
                     "mean_abs_error": group["recon_error"].abs().mean()})
    return pd.DataFrame(rows)


def hypothesis_comparison(leases: pd.DataFrame, concessions: pd.DataFrame, links: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Reconciliation rates under the working hypothesis and under the alternatives section 05 rejects. Aggregates only.

    Rows: `lump_once_all_codes` (the hypothesis), `lump_times_months` (PromoPay multiplied by its months value),
    `without_accessories` (free parking, locker and appliance credits left out). Columns: scenario, rate_all,
    rate_discounted, mean_abs_error.
    """
    scenarios = {
        "lump_once_all_codes": {},
        "lump_times_months": {"lump_multiplies_months": True},
        "without_accessories": {"exclude_codes": frozenset(ACCESSORY_CHARGE_CODES)},
    }
    rows = []
    for name, options in scenarios.items():
        rebuilt = reconstruct_net_rent(leases, concessions, links, **options)
        rows.append({"scenario": name, "rate_all": reconciliation_rate(rebuilt, cfg),
                     "rate_discounted": reconciliation_rate(rebuilt, cfg, only_discounted=True),
                     "mean_abs_error": float(rebuilt["recon_error"].abs().mean())})
    return pd.DataFrame(rows)


def divergence_by_year(leases: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    """Contractual vs net growth and discount intensity by year, to show when and why the two diverge. Aggregates only.

    Per year: n_leases, share of leases with a concession, mean discount share (1 - net/contract), and for eligible
    same-unit pairs the median annualized growth in percent on contract and net rent and their gap in percentage
    points (net minus contract).
    """
    starts = leases.assign(year=leases["lease_start"].dt.year,
                           discount=1 - leases["rent_net_all_incentives"] / leases["rent_contract"].where(leases["rent_contract"] > 0))
    by_lease = starts.groupby("year").agg(n_leases=("unit_id", "size"), share_with_concession=("has_concession", "mean"),
                                          mean_discount_share=("discount", "mean"))
    eligible = pairs[pairs["eligible"]]
    by_pair = eligible.groupby("year").agg(n_pairs=("unit_id", "size"),
                                           log_contract=("loggrowth_contract", "median"),
                                           log_net=("loggrowth_net", "median"))
    out = by_lease.join(by_pair, how="left")
    out["median_contract_pct"] = PERCENT * np.expm1(out["log_contract"])
    out["median_net_pct"] = PERCENT * np.expm1(out["log_net"])
    out["gap_pp"] = out["median_net_pct"] - out["median_contract_pct"]
    return out.drop(columns=["log_contract", "log_net"]).reset_index()
