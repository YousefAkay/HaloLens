"""Low / central / high scenarios.

Owner: FCT. Status: stub created by INT (I-01). Implement per AGENTS.md Section 7.3.
"""

from __future__ import annotations

import pandas as pd
from leaselens.contracts import ForecastResult


def scenario_table(result: ForecastResult, cfg: dict) -> pd.DataFrame:
    """Return headline under each scenario lever (forecast.yaml scenarios)."""
    raise NotImplementedError
