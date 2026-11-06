"""Naive vs fixed-mix same-unit growth and the contractual→net bridge.

Implements `rent_bridge` and `mix_by_year` for notebook section 03.

For each calendar year y the bridge decomposes, on the annual log scale (so the parts add exactly):

    naive (median rent of leases starting in y vs y-1)
      = same-unit contractual growth (fixed composition)
      + composition and other effects (the residual: mix of buildings, bedrooms, renewals, gaps)
    same-unit net growth = same-unit contractual growth + incentive effect (contractual→net)

The same-unit figures use exactly the headline machinery of the backtest (`forecast.baselines`): segment weights
frozen at December 31 of y-1, winsorization thresholds learned on pairs known at that cutoff. Weights describe the mix
of observed lease transitions, NOT portfolio occupancy or turnover rate. Output holds aggregates only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from halolens.config import cutoff_for
from halolens.contracts import PERCENT
from halolens.forecast.baselines import frozen_weights, headline_summary, winsor_bounds

BRIDGE_COLUMNS = [
    "year", "n_leases", "median_rent_contract", "median_rent_net",
    "naive_log_contract", "naive_log_net", "n_pairs", "weight_coverage",
    "same_unit_log_contract", "same_unit_log_net", "composition_log", "incentive_log",
    "naive_contract_pct", "naive_net_pct", "same_unit_contract_pct", "same_unit_net_pct",
    "composition_pp", "incentive_pp", "note",
]

NOTE_NO_WEIGHTS = "no eligible pairs in the weight window before the cutoff"
NOTE_NO_PAIRS = "no eligible pairs in a weighted segment this year"


def _pct(log_growth: float) -> float:
    """Annual log growth to percent; NaN stays NaN."""
    return float(PERCENT * np.expm1(log_growth))


def _same_unit_logs(pairs: pd.DataFrame, year: int, cfg: dict) -> tuple[dict, str]:
    """Fixed-composition same-unit log growth of `year` (weights and bounds frozen at that year's cutoff)."""
    eligible = pairs[pairs["eligible"]]
    cutoff = cutoff_for(year, cfg)
    known = eligible[(eligible["sign_date"] <= cutoff) & (eligible["lease_start"] <= cutoff)]
    empty = {"n_pairs": 0, "coverage": np.nan, "log_contract": np.nan, "log_net": np.nan}
    try:
        weights = frozen_weights(known, cutoff, cfg)
    except ValueError:
        return empty, NOTE_NO_WEIGHTS
    summary = headline_summary(eligible[eligible["year"] == year], weights, winsor_bounds(known, cfg), cfg)
    if summary is None:
        return empty, NOTE_NO_PAIRS
    return summary, ""


def rent_bridge(leases: pd.DataFrame, pairs: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Return yearly naive median growth, fixed-composition same-unit growth (contract and net) and the decomposition.

    Inputs: canonical LEASES; PAIRS from `build_pairs(leases, cfg)`; merged config (uses
    `composition.naive_years_start`, `headline.*`, `winsorize.*`, `forecast_years.cutoff_month_day`).
    Output: one row per year from `naive_years_start` to the last lease-start year (columns BRIDGE_COLUMNS).
    `*_log_*` columns are annual log growth; `*_pct` = 100 x (exp(log) - 1); `composition_pp` and `incentive_pp` are
    100 x the log differences, so naive = same-unit contract + composition and same-unit net = same-unit contract +
    incentive hold exactly in log points. A year whose same-unit figure cannot be computed keeps NaN and a `note`.
    Assumptions: the naive figure compares the median rent of ALL leases starting in the year (new leases and
    renewals) with the previous year's, which is what a simple year-over-year reading of the extract gives.
    """
    first_year = cfg["composition"]["naive_years_start"]
    starts = leases["lease_start"].dt.year
    medians = leases.assign(year=starts).groupby("year").agg(
        n_leases=("unit_id", "size"), median_rent_contract=("rent_contract", "median"),
        median_rent_net=("rent_net_all_incentives", "median"))
    last_year = int(starts.max())

    rows = []
    for year in range(first_year, last_year + 1):
        row = {"year": year, "n_leases": 0, "median_rent_contract": np.nan, "median_rent_net": np.nan}
        if year in medians.index:
            row.update(medians.loc[year].to_dict())
        for kind, column in (("contract", "median_rent_contract"), ("net", "median_rent_net")):
            previous = medians[column].get(year - 1, np.nan)
            row[f"naive_log_{kind}"] = float(np.log(row[column] / previous)) if previous > 0 else np.nan
        summary, note = _same_unit_logs(pairs, year, cfg)
        row.update(n_pairs=summary["n_pairs"], weight_coverage=summary["coverage"],
                   same_unit_log_contract=summary["log_contract"], same_unit_log_net=summary["log_net"], note=note)
        rows.append(row)

    bridge = pd.DataFrame(rows)
    bridge["n_leases"] = bridge["n_leases"].astype(int)
    bridge["n_pairs"] = bridge["n_pairs"].astype(int)
    bridge["composition_log"] = bridge["naive_log_contract"] - bridge["same_unit_log_contract"]
    bridge["incentive_log"] = bridge["same_unit_log_net"] - bridge["same_unit_log_contract"]
    for kind in ("contract", "net"):
        bridge[f"naive_{kind}_pct"] = bridge[f"naive_log_{kind}"].map(_pct)
        bridge[f"same_unit_{kind}_pct"] = bridge[f"same_unit_log_{kind}"].map(_pct)
    bridge["composition_pp"] = PERCENT * bridge["composition_log"]
    bridge["incentive_pp"] = PERCENT * bridge["incentive_log"]
    return bridge[BRIDGE_COLUMNS]


def mix_by_year(leases: pd.DataFrame, column: str, cfg: dict) -> pd.DataFrame:
    """Share of leases starting each year by `column` (e.g. building, beds, is_renewal). Aggregates only.

    Rows: years from `composition.naive_years_start`; columns: the values of `column`; cells: shares summing to 1.
    Shows how the mix behind the naive median moves from one year to the next.
    """
    first_year = cfg["composition"]["naive_years_start"]
    years = leases["lease_start"].dt.year.rename("year")
    counts = pd.crosstab(years, leases[column])
    counts = counts[counts.index >= first_year]
    return counts.div(counts.sum(axis=1), axis=0)
