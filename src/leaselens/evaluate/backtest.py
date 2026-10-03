"""Time-respecting backtests on 2023-2025.

Owner: FCT. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd
from leaselens.contracts import BacktestResult, CanonicalTables


def actual_for_year(tables: CanonicalTables, year: int, weights: pd.DataFrame, cfg: dict) -> dict:
    """Actual headline for `year` with weights frozen at that year's cutoff."""
    raise NotImplementedError


def run_backtest(tables: CanonicalTables, external: pd.DataFrame, target_year: int, cfg: dict) -> BacktestResult:
    """Forecast as of Dec 31 of target_year - 1 with forecast.combine.forecast, then compare with the actual."""
    raise NotImplementedError
