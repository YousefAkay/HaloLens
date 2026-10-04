"""Internal same-unit trend vs CMHC / CPI market trends.

Owner: MSR. Implements `reconcile`, `reconcile_summary` and `provenance_table` for notebook section 07.

Each comparison in `measure.yaml` (`reconcile_market.comparisons`) puts one internal cut of the eligible same-unit
pairs (all leases, renewals or turnovers; optionally one bedroom count) next to one public series per province:
Québec leases vs the Montréal CMA (or Québec rent CPI), Ontario leases vs the Ottawa CMA (or Ontario rent CPI).
A province is never compared with the other province's market. This is descriptive history: it never feeds the
forecast. CMHC vacancy is listed as regional context only and is never a project occupancy figure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from leaselens.config import external_cutoff_for
from leaselens.forecast.baselines import GROWTH_CONTRACT, GROWTH_NET, to_pct
from leaselens.measure.renewals import clip_by_year

RECONCILE_COLUMNS = [
    "comparison", "label", "province", "geography", "year", "lease_type", "beds", "n_pairs",
    "internal_contract_pct", "internal_net_pct", "market_series", "market_pct", "gap_contract_pp", "gap_net_pp",
    "release_date", "known_by_next_info_date",
]
SUMMARY_COLUMNS = [
    "comparison", "label", "province", "geography", "n_years", "mean_gap_contract_pp", "mean_abs_gap_contract_pp",
    "mean_gap_net_pp",
]
PROVENANCE_COLUMNS = [
    "series_id", "publisher", "geography", "metric", "role", "n_observations", "first_period", "last_period",
    "last_release_date", "extracted_by", "verified", "url",
]
ALL = "all"
LEASE_TYPE_RENEWAL = {"renewal": True, "turnover": False}
ROLE_COMPARED = "compared"
ROLE_CONTEXT = "context_only"
ROLE_REFERENCE = "reference"


def _internal_growth(clipped: pd.DataFrame, comparison: dict, min_pairs: int) -> pd.DataFrame:
    """Mean annualized growth (contract and net, %) by year x province for one internal cut; thin cells -> NaN."""
    rows = clipped
    if comparison["lease_type"] != ALL:
        rows = rows[rows["is_renewal"] == LEASE_TYPE_RENEWAL[comparison["lease_type"]]]
    if comparison.get("beds") is not None:
        rows = rows[rows["beds"] == comparison["beds"]]
    cells = rows.groupby(["year", "province"], observed=True).agg(
        n_pairs=("unit_id", "size"), log_contract=(GROWTH_CONTRACT, "mean"), log_net=(GROWTH_NET, "mean"),
    ).reset_index()
    thin = cells["n_pairs"] < min_pairs
    cells.loc[thin, ["log_contract", "log_net"]] = np.nan
    cells["internal_contract_pct"] = cells["log_contract"].map(to_pct)
    cells["internal_net_pct"] = cells["log_net"].map(to_pct)
    return cells.drop(columns=["log_contract", "log_net"])


def _market_values(external: pd.DataFrame, series: dict) -> pd.DataFrame:
    """One value per province x year (year of ref_period_end); the latest release wins when a value was revised."""
    parts = []
    for province, series_id in series.items():
        rows = external[external["series_id"] == series_id]
        parts.append(rows.assign(province=province, year=rows["ref_period_end"].dt.year.astype(int)))
    if not parts:
        return pd.DataFrame(columns=["province", "year", "geography", "market_series", "market_pct", "release_date"])
    market = pd.concat(parts).sort_values("release_date").drop_duplicates(["province", "year"], keep="last")
    return market.rename(columns={"series_id": "market_series", "value": "market_pct"})[
        ["province", "year", "geography", "market_series", "market_pct", "release_date"]]


def reconcile(pairs: pd.DataFrame, external: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Return internal vs market growth per year and geography, with the gap.

    Inputs: PAIRS from `build_pairs` (eligible rows only), the EXTERNAL table (`load_external`), merged config
    (`reconcile_market.*`, `renewals.min_pairs_per_cell`, `winsorize.*`). Internal growth is the equal-weight mean of
    annualized log growth per year x province, clipped at bounds learned on pairs known at Dec 31 of y-1 (same rule
    as section 06), shown as 100 x (exp(mean) - 1). `gap_*_pp` = internal % - market %. `year` is the later lease's
    start year for pairs and the year the reference period ends for public series (CMHC October survey, CPI annual
    average): the timing is close, not identical. `known_by_next_info_date` tells whether the market value was public
    by the information date of the next forecast (Jan 31 of year + 1). Output columns RECONCILE_COLUMNS, aggregates
    only; a year with only one side present keeps NaN on the missing side.
    """
    settings = cfg["reconcile_market"]
    min_pairs = cfg["renewals"]["min_pairs_per_cell"]
    eligible = pairs[pairs["eligible"] & (pairs["year"] >= settings["first_year"])]
    clipped = clip_by_year(eligible, cfg) if not eligible.empty else eligible
    parts = []
    for comparison in settings["comparisons"]:
        internal = _internal_growth(clipped, comparison, min_pairs)
        market = _market_values(external[external["ref_period_end"].dt.year >= settings["first_year"]],
                                comparison["series"])
        merged = internal.merge(market, on=["year", "province"], how="outer")
        merged = merged[merged["province"].isin(list(comparison["series"]))]
        parts.append(merged.assign(comparison=comparison["name"], label=comparison["label"],
                                   lease_type=comparison["lease_type"],
                                   beds=ALL if comparison.get("beds") is None else str(comparison["beds"])))
    if not parts:
        return pd.DataFrame(columns=RECONCILE_COLUMNS)
    table = pd.concat(parts, ignore_index=True)
    table["n_pairs"] = table["n_pairs"].fillna(0).astype(int)
    table["gap_contract_pp"] = table["internal_contract_pct"] - table["market_pct"]
    table["gap_net_pp"] = table["internal_net_pct"] - table["market_pct"]
    next_info = table["year"].map(lambda year: external_cutoff_for(int(year) + 1, cfg))
    table["known_by_next_info_date"] = table["release_date"].notna() & (table["release_date"] <= next_info)
    table["year"] = table["year"].astype(int)
    order = {comparison["name"]: rank for rank, comparison in enumerate(settings["comparisons"])}
    table = table.sort_values(["comparison", "province", "year"], key=lambda column: column.map(order)
                              if column.name == "comparison" else column)
    return table[RECONCILE_COLUMNS].reset_index(drop=True)


def reconcile_summary(table: pd.DataFrame) -> pd.DataFrame:
    """Per comparison x province: years with both sides, mean signed and mean absolute gap (pp).

    Input: `reconcile` output. A positive mean gap means the extract grew faster than the public series.
    Output columns SUMMARY_COLUMNS, in the input's comparison order.
    """
    both = table.dropna(subset=["internal_contract_pct", "market_pct"])
    if both.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    summary = both.groupby(["comparison", "label", "province"], sort=False).agg(
        geography=("geography", "first"), n_years=("year", "size"),
        mean_gap_contract_pp=("gap_contract_pp", "mean"),
        mean_abs_gap_contract_pp=("gap_contract_pp", lambda gaps: gaps.abs().mean()),
        mean_gap_net_pp=("gap_net_pp", "mean"),
    ).reset_index()
    return summary[SUMMARY_COLUMNS]


def provenance_table(external: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """One row per public series: publisher, geography, coverage, last release date, provenance and its role here.

    `role` is "compared" (used in a `reconcile_market` comparison), "context_only" (metrics in
    `reconcile_market.context_only_metrics`, e.g. CMHC vacancy: regional context, never a project figure) or
    "reference" (any other series, e.g. regulatory percentages used in section 06 or monthly CPI levels).
    `verified` is True when every row of the series has `verified_by`. `url` is the URL of the latest release.
    """
    settings = cfg["reconcile_market"]
    compared = {series_id for comparison in settings["comparisons"] for series_id in comparison["series"].values()}
    if external.empty:
        return pd.DataFrame(columns=PROVENANCE_COLUMNS)
    latest = external.sort_values("release_date").groupby("series_id").tail(1).set_index("series_id")
    table = external.groupby("series_id").agg(
        publisher=("publisher", "first"), geography=("geography", "first"), metric=("metric", "first"),
        n_observations=("value", "size"), first_period=("ref_period_start", "min"),
        last_period=("ref_period_end", "max"), last_release_date=("release_date", "max"),
        extracted_by=("extracted_by", lambda values: ", ".join(sorted(set(values)))),
        verified=("verified_by", lambda values: bool((values != "").all())),
    )
    table["url"] = latest["url"]
    table = table.reset_index()
    table["role"] = np.select(
        [table["series_id"].isin(compared), table["metric"].isin(settings["context_only_metrics"])],
        [ROLE_COMPARED, ROLE_CONTEXT], default=ROLE_REFERENCE)
    return table[PROVENANCE_COLUMNS].sort_values(["role", "series_id"]).reset_index(drop=True)
