"""Time-respecting backtests on 2023-2025.

Owner: FCT. Implements AGENTS.md Section 7.3. Every fold forecasts as of December 31 of the year before the target
through `make_snapshot`, then compares with the actual of that year under the same headline definition.
`run_backtest` uses `forecast.combine.forecast` (F-05); `backtest_baselines` runs B0-B2 through the same machinery.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
from leaselens.config import cutoff_for
from leaselens.contracts import BacktestResult, CanonicalTables, ForecastResult, Snapshot
from leaselens.evaluate.metrics import absolute_error_pp, signed_error_pp
from leaselens.forecast.asof import make_snapshot
from leaselens.forecast.baselines import (BASELINES, frozen_weights, headline_summary, to_pct, training_pairs,
                                          winsor_bounds)
from leaselens.forecast.combine import forecast
from leaselens.measure.pairs import build_pairs

Forecaster = Callable[[Snapshot, dict], ForecastResult]


def actual_for_year(tables: CanonicalTables, year: int, weights: pd.DataFrame, cfg: dict) -> dict:
    """Actual headline for `year` with weights frozen at that year's cutoff.

    Pairs are eligible same-unit pairs whose later lease starts in `year`. Winsorization thresholds are learned on
    pairs known at the year's cutoff, not on the year itself. Returns net_pct, contract_pct, median_net_pct,
    median_contract_pct, n_pairs, weight_coverage and the per-segment table; raises ValueError without pairs.
    """
    pairs = build_pairs(tables.leases, cfg)
    pairs = pairs[pairs["eligible"]]
    cutoff = cutoff_for(year, cfg)
    known = pairs[(pairs["sign_date"] <= cutoff) & (pairs["lease_start"] <= cutoff)]
    summary = headline_summary(pairs[pairs["year"] == year], weights, winsor_bounds(known, cfg), cfg)
    if summary is None:
        raise ValueError(f"No eligible pairs with weighted segments in {year}")
    return {
        "net_pct": to_pct(summary["log_net"]), "contract_pct": to_pct(summary["log_contract"]),
        "median_net_pct": to_pct(summary["log_median_net"]),
        "median_contract_pct": to_pct(summary["log_median_contract"]),
        "n_pairs": summary["n_pairs"], "weight_coverage": summary["coverage"], "segments": summary["segments"],
    }


def _fold(forecaster: Forecaster, tables: CanonicalTables, external: pd.DataFrame, target_year: int,
          cfg: dict) -> BacktestResult:
    """One backtest fold: snapshot at the target year's cutoff, forecast, then the actual."""
    cutoff = cutoff_for(target_year, cfg)
    snapshot = make_snapshot(tables, external, cutoff)
    result = forecaster(snapshot, cfg)
    weights = frozen_weights(training_pairs(snapshot, cfg), cutoff, cfg)
    actual = actual_for_year(tables, target_year, weights, cfg)
    return BacktestResult(
        target_year=target_year, forecast=result,
        actual_net_pct=actual["net_pct"], actual_contract_pct=actual["contract_pct"],
        error_pp_net=signed_error_pp(result.headline_net_pct, actual["net_pct"]),
        error_pp_contract=signed_error_pp(result.headline_contract_pct, actual["contract_pct"]),
        coverage={"n_pairs_actual": actual["n_pairs"], "weight_coverage": actual["weight_coverage"],
                  "n_leases_known": len(snapshot.leases)})


def run_backtest(tables: CanonicalTables, external: pd.DataFrame, target_year: int, cfg: dict) -> BacktestResult:
    """Forecast as of Dec 31 of target_year - 1 with forecast.combine.forecast, then compare with the actual."""
    return _fold(forecast, tables, external, target_year, cfg)


def backtest_baselines(tables: CanonicalTables, external: pd.DataFrame, cfg: dict,
                       years: list[int] | None = None) -> pd.DataFrame:
    """Backtest table for B0-B2: one row per model x year with forecast, actual and errors (pp). Aggregates only.

    A baseline that cannot run for a fold (for example B2 without released market data) keeps its row with NaN
    values and the reason in `note`, so a losing or missing model stays visible.
    """
    years = years if years is not None else cfg["forecast_years"]["backtest_years"]
    rows = []
    for name, forecaster in BASELINES.items():
        for year in years:
            row = {"model": name, "year": year, "forecast_net_pct": np.nan, "actual_net_pct": np.nan,
                   "error_pp_net": np.nan, "abs_error_pp_net": np.nan, "error_pp_contract": np.nan, "note": ""}
            try:
                fold = _fold(forecaster, tables, external, year, cfg)
            except ValueError as problem:
                row["note"] = str(problem)
            else:
                row.update(forecast_net_pct=fold.forecast.headline_net_pct, actual_net_pct=fold.actual_net_pct,
                           error_pp_net=fold.error_pp_net,
                           abs_error_pp_net=absolute_error_pp(fold.forecast.headline_net_pct, fold.actual_net_pct),
                           error_pp_contract=fold.error_pp_contract)
            rows.append(row)
    return pd.DataFrame(rows)
