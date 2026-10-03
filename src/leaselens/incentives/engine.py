"""Discount-share trend per segment (renewals and turnovers separately).

Owner: FCT. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd
from leaselens.contracts import Snapshot


def forecast_discount(snapshot: Snapshot, cfg: dict) -> pd.DataFrame:
    """Return per segment the current discount share d0 and forecast d1, where discount = 1 - net/contract."""
    raise NotImplementedError
