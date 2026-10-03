"""Export aggregate results only (no unit-level data) to JSON.

Owner: INT. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd



def export(results: dict, path) -> None:
    """Write headline, companions, backtest table, coverage and scenarios to JSON. Rejects unit-level fields."""
    raise NotImplementedError
