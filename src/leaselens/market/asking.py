"""Asking-rent leading indicator for turnover rents.

Owner: MSR. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd
from leaselens.contracts import Snapshot


def turnover_signal(snapshot: Snapshot, cfg: dict) -> pd.DataFrame:
    """Return expected turnover log growth per segment from asking rents posted before the cutoff, net of the asking→signed spread learned on training years."""
    raise NotImplementedError
