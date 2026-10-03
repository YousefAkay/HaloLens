"""Reconstruction of net rent from concession records.

Owner: FCT. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd



def reconstruct_net_rent(leases: pd.DataFrame, concessions: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    """Return per lease the reconstructed net rent (lump credits once, monthly credits x months, spread over the term) and the reconciliation error."""
    raise NotImplementedError
