"""Error metrics in percentage points.

Owner: FCT. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd



def signed_error_pp(forecast_pct: float, actual_pct: float) -> float:
    """Forecast minus actual, in percentage points."""
    raise NotImplementedError


def absolute_error_pp(forecast_pct: float, actual_pct: float) -> float:
    """Absolute error in percentage points."""
    raise NotImplementedError
