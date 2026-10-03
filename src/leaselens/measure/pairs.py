"""Consecutive-lease matching on the safe unit key with an exclusion audit.

Owner: MSR. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd



def build_pairs(leases: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Return a PAIRS table (contracts.PAIRS_COLUMNS) with eligible flag and exclusion_reason for every consecutive pair."""
    raise NotImplementedError
