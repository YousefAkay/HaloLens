"""Point-in-time snapshots: the single anti-leakage chokepoint.

Owner: FCT. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd
from leaselens.contracts import CanonicalTables, Snapshot


def make_snapshot(tables: CanonicalTables, external: pd.DataFrame, cutoff: pd.Timestamp) -> Snapshot:
    """Filter every table to what was knowable at cutoff (AGENTS.md Section 9.3)."""
    raise NotImplementedError
