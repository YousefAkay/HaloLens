"""External observation registry with release-date filtering.

Owner: MSR. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd



def load_external(path) -> pd.DataFrame:
    """Read data/public/sources.csv into contracts.EXTERNAL_COLUMNS with parsed dates."""
    raise NotImplementedError


def as_of(external: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Keep only observations whose release_date is on or before cutoff."""
    raise NotImplementedError
