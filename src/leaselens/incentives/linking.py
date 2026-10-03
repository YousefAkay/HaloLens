"""Concession→lease candidate generation and assignment.

Owner: FCT. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd



def link_concessions(concessions: pd.DataFrame, leases: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Return a LINKS table: candidates = same unit, signed on/before date_from, still active; resolve ties by reconciliation fit."""
    raise NotImplementedError
