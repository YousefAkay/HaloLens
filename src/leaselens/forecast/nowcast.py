"""Small local-trend / state-space model on the monthly index.

Owner: FCT. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd



def nowcast(index: pd.DataFrame, cutoff: pd.Timestamp, cfg: dict) -> dict:
    """Return the trend estimate at cutoff and its 12-month-ahead projection."""
    raise NotImplementedError
