"""Renewal vs turnover summaries by year and province.

Owner: MSR. Implements `split_summary` (AGENTS.md Section 7.3) for notebook section 06.

Renewals (`is_renewal` true, source `sRenewal`) and turnovers (a new tenant) follow different rules in each province
(see `market.regulation`), so their growth is always shown separately and never pooled across provinces.
Growth is clipped at winsorization thresholds learned, for each year y, on the pairs known at December 31 of y-1
(the same training-only rule as the headline). Output holds aggregates only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from leaselens.config import cutoff_for
from leaselens.contracts import PERCENT
from leaselens.forecast.baselines import GROWTH_CONTRACT, GROWTH_NET, to_pct, winsor_bounds

SPLIT_KEYS = ["year", "province", "is_renewal"]
SPLIT_COLUMNS = SPLIT_KEYS + [
    "lease_type", "n_pairs", "mean_contract_pct", "mean_net_pct", "median_contract_pct", "median_net_pct",
    "incentive_pp", "note",
]
LEASE_TYPE = {True: "renewal", False: "turnover"}
NOTE_THIN_CELL = "fewer pairs than renewals.min_pairs_per_cell: growth not shown"


def clip_by_year(eligible: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Clip each year's growth at thresholds learned on the pairs known at that year's cutoff (training only)."""
    clipped = []
    for year, group in eligible.groupby("year"):
        cutoff = cutoff_for(int(year), cfg)
        known = eligible[(eligible["sign_date"] <= cutoff) & (eligible["lease_start"] <= cutoff)]
        group = group.copy()
        if not known.empty:
            for column, (low, high) in winsor_bounds(known, cfg).items():
                group[column] = group[column].clip(low, high)
        clipped.append(group)
    return pd.concat(clipped) if clipped else eligible.copy()


def split_summary(pairs: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Return counts and growth (contract and net) by year x province x is_renewal.

    Input: PAIRS from `build_pairs` (only `eligible` rows are used); merged config (`renewals.min_pairs_per_cell`,
    `winsorize.*`, `forecast_years.cutoff_month_day`). Output columns SPLIT_COLUMNS, one row per observed cell:
    `mean_*_pct` = 100 x (exp(mean annual log growth) - 1); `median_*_pct` likewise from the median log growth;
    `incentive_pp` = 100 x (mean log net - mean log contract), the contractual→net gap in log points.
    A cell with fewer than `min_pairs_per_cell` pairs keeps its count but NaN growth and a `note`.
    Assumption: these are plain (equal-weight) averages within a cell, not the fixed-weight headline.
    """
    min_pairs = cfg["renewals"]["min_pairs_per_cell"]
    eligible = pairs[pairs["eligible"]]
    if eligible.empty:
        return pd.DataFrame(columns=SPLIT_COLUMNS)
    clipped = clip_by_year(eligible, cfg)
    cells = clipped.groupby(SPLIT_KEYS, observed=True).agg(
        n_pairs=("unit_id", "size"),
        mean_log_contract=(GROWTH_CONTRACT, "mean"), mean_log_net=(GROWTH_NET, "mean"),
        median_log_contract=(GROWTH_CONTRACT, "median"), median_log_net=(GROWTH_NET, "median"),
    ).reset_index()

    thin = cells["n_pairs"] < min_pairs
    log_columns = [f"{stat}_log_{kind}" for stat in ("mean", "median") for kind in ("contract", "net")]
    cells.loc[thin, log_columns] = np.nan
    for stat in ("mean", "median"):
        for kind in ("contract", "net"):
            cells[f"{stat}_{kind}_pct"] = cells[f"{stat}_log_{kind}"].map(to_pct)
    cells["incentive_pp"] = PERCENT * (cells["mean_log_net"] - cells["mean_log_contract"])
    cells["lease_type"] = cells["is_renewal"].map(LEASE_TYPE)
    cells["note"] = np.where(thin, NOTE_THIN_CELL, "")
    cells["year"] = cells["year"].astype(int)
    cells["n_pairs"] = cells["n_pairs"].astype(int)
    return cells[SPLIT_COLUMNS].sort_values(SPLIT_KEYS).reset_index(drop=True)
