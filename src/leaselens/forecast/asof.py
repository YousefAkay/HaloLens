"""Point-in-time snapshots: the single anti-leakage chokepoint.

Owner: FCT. Implements `make_snapshot` (AGENTS.md Section 7.3). Every forecast and backtest reads its data
through this function, so the time policy of Section 9.3 lives in one place.
"""

from __future__ import annotations

import pandas as pd
from leaselens.contracts import CanonicalTables, Snapshot


def make_snapshot(tables: CanonicalTables, external: pd.DataFrame, cutoff: pd.Timestamp) -> Snapshot:
    """Filter every table to what was knowable at `cutoff` (AGENTS.md Section 9.3). Inputs are not modified.

    - leases: BOTH `sign_date` and `lease_start` on or before the cutoff (a lease signed earlier that starts
      later is not training data).
    - concessions: `date_from` on or before the cutoff.
    - asking: `month` on or before the month containing the cutoff.
    - external: `release_date` on or before the cutoff (same rule as `market.registry.as_of`; applied here directly
      so the snapshot does not depend on MSR's loader).
    - units (listings): the table is a 2025 snapshot, so it is kept only when every row's `snapshot_month` is on
      or before the cutoff's month; otherwise it is None (never used for historical folds).
    The cutoff day itself is inclusive everywhere.
    """
    cutoff = pd.Timestamp(cutoff)
    cutoff_month = cutoff.to_period("M")

    leases = tables.leases
    known_leases = leases[(leases["sign_date"] <= cutoff) & (leases["lease_start"] <= cutoff)]
    concessions = tables.concessions[tables.concessions["date_from"] <= cutoff]
    asking = tables.asking[tables.asking["month"] <= cutoff_month]
    released = external[external["release_date"] <= cutoff]

    units = tables.units
    units_knowable = units is not None and len(units) > 0 and bool((units["snapshot_month"] <= cutoff_month).all())

    return Snapshot(
        cutoff=cutoff,
        leases=known_leases.copy(),
        concessions=concessions.copy(),
        asking=asking.copy(),
        units=units.copy() if units_knowable else None,
        external=released.copy(),
    )
