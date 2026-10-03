"""Error metrics in percentage points.

Owner: FCT. Implements AGENTS.md Section 7.3 (errors are forecast minus actual, both in percent).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def signed_error_pp(forecast_pct: float, actual_pct: float) -> float:
    """Forecast minus actual, in percentage points (positive = over-forecast)."""
    return float(forecast_pct - actual_pct)


def absolute_error_pp(forecast_pct: float, actual_pct: float) -> float:
    """Absolute error in percentage points."""
    return abs(signed_error_pp(forecast_pct, actual_pct))


def mean_absolute_error_pp(errors_pp: pd.Series | list[float]) -> float:
    """Mean of absolute errors (pp); NaN errors are ignored, NaN if none remain. Champion metric in forecast.yaml."""
    values = pd.Series(errors_pp, dtype=float).dropna()
    return float(np.abs(values).mean()) if len(values) else float("nan")
