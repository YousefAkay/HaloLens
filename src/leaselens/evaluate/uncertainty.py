"""Unit-cluster bootstrap: resample whole unit histories and recompute the headline.

Owner: INT. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd
from leaselens.contracts import CanonicalTables


def unit_bootstrap(tables: CanonicalTables, external: pd.DataFrame, cfg: dict, n_boot: int) -> pd.DataFrame:
    """Return one row per bootstrap draw with the recomputed headline (seed from core.yaml)."""
    raise NotImplementedError
