"""Internal same-unit trend vs CMHC / CPI market trends.

Owner: MSR. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd



def reconcile(pairs: pd.DataFrame, external: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Return internal vs market growth per year and geography, with the gap."""
    raise NotImplementedError
