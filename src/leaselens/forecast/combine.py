"""Renewal + turnover + incentive engines combined with fixed weights.

Owner: FCT. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd
from leaselens.contracts import ForecastResult, Snapshot


def forecast(snapshot: Snapshot, cfg: dict) -> ForecastResult:
    """The single forecasting pipeline used by estimate_2026() and backtest()."""
    raise NotImplementedError
