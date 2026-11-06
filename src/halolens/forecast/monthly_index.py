"""Monthly same-unit rent index built from PAIRS.

Implements `build_monthly_index`. Each month holds the fixed-weight headline
of the eligible pairs whose later lease starts in that month: annualized log growth, winsorized at bounds learned on the
given pairs, aggregated with segment weights frozen at the cutoff. Months with too few pairs borrow neighbouring months.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from halolens.contracts import PERCENT
from halolens.forecast.baselines import frozen_weights, headline_summary, winsor_bounds

INDEX_COLUMNS = ["month", "n_pairs", "n_pairs_used", "pool_radius", "weight_coverage", "log_net", "log_contract",
                 "pct_net", "pct_contract"]


def _pool_radius(counts: pd.Series, month: pd.Period, min_pairs: int, max_radius: int) -> tuple[int, int]:
    """Smallest radius (months on each side) giving at least `min_pairs` pairs, capped at `max_radius`; and the count."""
    radius, used = 0, int(counts.get(month, 0))
    while used < min_pairs and radius < max_radius:
        radius += 1
        window = [month + offset for offset in range(-radius, radius + 1)]
        used = int(counts.reindex(window, fill_value=0).sum())
    return radius, used


def build_monthly_index(pairs: pd.DataFrame, cfg: dict, cutoff: pd.Timestamp | None = None) -> pd.DataFrame:
    """Return a monthly index (contract and net) with pair counts per month.

    Inputs: eligible PAIRS known at the cutoff (use `baselines.training_pairs` on a snapshot); `cutoff` freezes the
    segment weights and defaults to the last pair's lease start. Pairs are placed in the month of their later
    `lease_start`. Thin months (< `nowcast.min_pairs_per_month`) pool up to `nowcast.max_pool_months` neighbours on each
    side; pooled windows overlap, so neighbouring months are smoothed on purpose. Months still empty are NaN.
    Columns: month (Period[M], every month from the first to the last pair), n_pairs (own), n_pairs_used (after
    pooling), pool_radius, weight_coverage, log_net, log_contract (annualized log growth), pct_net, pct_contract.
    Winsor bounds come from the given pairs only. Aggregates only: no unit-level data in the output.
    """
    if pairs.empty:
        raise ValueError("No pairs to build a monthly index from")
    settings = cfg["nowcast"]
    cutoff = pd.Timestamp(cutoff) if cutoff is not None else pairs["lease_start"].max()
    weights = frozen_weights(pairs, cutoff, cfg)
    bounds = winsor_bounds(pairs, cfg)

    months = pairs["lease_start"].dt.to_period("M")
    counts = months.value_counts()
    rows = []
    for month in pd.period_range(months.min(), months.max(), freq="M"):
        radius, used = _pool_radius(counts, month, settings["min_pairs_per_month"], settings["max_pool_months"])
        in_window = (months >= month - radius) & (months <= month + radius)
        summary = headline_summary(pairs[in_window], weights, bounds, cfg) if used else None
        row = {"month": month, "n_pairs": int(counts.get(month, 0)), "n_pairs_used": used, "pool_radius": radius,
               "weight_coverage": np.nan, "log_net": np.nan, "log_contract": np.nan}
        if summary is not None:
            row.update(weight_coverage=summary["coverage"], log_net=summary["log_net"],
                       log_contract=summary["log_contract"])
        rows.append(row)
    index = pd.DataFrame(rows)
    index["pct_net"] = PERCENT * np.expm1(index["log_net"])
    index["pct_contract"] = PERCENT * np.expm1(index["log_contract"])
    return index[INDEX_COLUMNS]
