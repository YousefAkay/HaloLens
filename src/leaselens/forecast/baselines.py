"""Baseline forecasts B0 (last year), B1 (trailing mean), B2 (market anchor + gap).

Owner: FCT. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd
from leaselens.contracts import ForecastResult, Snapshot


def last_year(snapshot: Snapshot, cfg: dict) -> ForecastResult:
    """B0: previous year's growth under the headline definition."""
    raise NotImplementedError


def trailing_mean(snapshot: Snapshot, cfg: dict) -> ForecastResult:
    """B1: mean of the trailing window (forecast.yaml baselines.trailing_window_years)."""
    raise NotImplementedError


def market_anchor(snapshot: Snapshot, cfg: dict) -> ForecastResult:
    """B2: latest released market growth plus the historical internal-vs-market gap."""
    raise NotImplementedError
