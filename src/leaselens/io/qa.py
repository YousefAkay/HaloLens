"""Structural QA on the source and canonical tables. Owner: INT.

Returns counts only — never rows — so the output is safe to show in the notebook.
"""

from __future__ import annotations

import pandas as pd

from leaselens.contracts import CanonicalTables

SAFE_UNIT_KEY = ["sPropCode", "sUnitCode"]
UNSAFE_UNIT_KEY = ["sSite", "sUnitCode"]


def _check(name: str, passed: bool, count, detail: str = "") -> dict:
    return {"check": name, "status": "pass" if passed else "FLAG", "count": count, "detail": detail}


def run_qa(raw: dict[str, pd.DataFrame], tables: CanonicalTables, data_end_date: str) -> pd.DataFrame:
    """Run the structural checks. `data_end_date` comes from config (core.yaml data.data_end_date)."""
    listings, leases_raw = raw["listings"], raw["leases"]
    concessions_raw, asking_raw = raw["concessions"], raw["asking"]
    leases = tables.leases
    end = pd.Timestamp(data_end_date)
    rows = []

    for name, df in raw.items():
        rows.append(_check(f"{name}: rows", True, len(df), f"{df.shape[1]} columns"))
        rows.append(_check(f"{name}: missing cells", df.isna().sum().sum() == 0, int(df.isna().sum().sum())))
        rows.append(_check(f"{name}: exact duplicate rows", not df.duplicated().any(), int(df.duplicated().sum())))

    safe_dupes = listings.duplicated(SAFE_UNIT_KEY).sum()
    rows.append(_check("listings: sPropCode+sUnitCode unique", safe_dupes == 0, int(safe_dupes)))
    unsafe_collisions = listings.duplicated(UNSAFE_UNIT_KEY, keep=False).sum()
    rows.append(_check("listings: units colliding on unsafe sSite+sUnitCode", True, int(unsafe_collisions),
                       "expected > 0: demonstrates why sSite must never be a key"))

    key_per_unit = leases_raw.groupby("hUnit")[SAFE_UNIT_KEY].nunique().max().max()
    unit_per_key = leases_raw.groupby(SAFE_UNIT_KEY)["hUnit"].nunique().max()
    rows.append(_check("leases: hUnit ↔ sPropCode+sUnitCode one-to-one", key_per_unit == 1 and unit_per_key == 1,
                       int(max(key_per_unit, unit_per_key))))
    link_per_unit = leases_raw.groupby("sLink")["hUnit"].nunique().max()
    rows.append(_check("leases: sLink ↔ hUnit one-to-one", link_per_unit == 1, int(link_per_unit)))

    leading_zero = listings["sUnitCode"].str.startswith("0").sum()
    rows.append(_check("listings: unit codes with leading zero (kept as text)", True, int(leading_zero)))

    renewal_values = set(leases_raw["sRenewal"].unique())
    rows.append(_check("leases: sRenewal only 0/1", renewal_values <= {0, 1}, len(renewal_values)))
    first_lease_renewals = int(((leases["lease_seq"] == 1) & leases["is_renewal"]).sum())
    rows.append(_check("leases: first lease never a renewal", first_lease_renewals == 0, first_lease_renewals))

    dup_start = leases.duplicated(["unit_id", "lease_start"]).sum()
    rows.append(_check("leases: no duplicate unit + lease start", dup_start == 0, int(dup_start)))
    ordered = leases.sort_values(["unit_id", "lease_start"])
    seq_not_increasing = int((ordered.groupby("unit_id")["lease_seq"].diff().dropna() <= 0).sum())
    rows.append(_check("leases: lease_seq increases with lease_start", seq_not_increasing == 0, seq_not_increasing))
    previous_end = ordered.groupby("unit_id")["lease_end"].shift()
    overlaps = int((previous_end >= ordered["lease_start"]).sum())
    rows.append(_check("leases: consecutive leases never overlap", overlaps == 0, overlaps))

    available_equal = int((leases_raw["sAvailable"] == leases_raw["sLeaseFrom"]).sum())
    rows.append(_check("leases: sAvailable == sLeaseFrom (column dropped)", available_equal == len(leases_raw),
                       available_equal))

    positive = int(((leases["rent_contract"] > 0) & (leases["rent_net_all_incentives"] > 0)).sum())
    rows.append(_check("leases: rents positive", positive == len(leases), positive))
    net_above_contract = int((leases["rent_net_all_incentives"] > leases["rent_contract"]).sum())
    rows.append(_check("leases: net rent never above contractual", net_above_contract == 0, net_above_contract))
    flag_mismatch = int((leases["has_concession"] != (leases["rent_net_all_incentives"] < leases["rent_contract"])).sum())
    rows.append(_check("leases: has_concession ⇔ net < contractual", flag_mismatch == 0, flag_mismatch))

    sign_after_start = int((leases["sign_date"] > leases["lease_start"]).sum())
    rows.append(_check("leases: sign_date on/before lease_start", sign_after_start == 0, sign_after_start))
    beyond_end = int(((leases["sign_date"] > end) | (leases["lease_start"] > end)).sum())
    rows.append(_check("leases: no signing/start after data end date", beyond_end == 0, beyond_end))
    future_end = int((leases["lease_end"] > end).sum())
    rows.append(_check("leases: contractual end dates after data end date", True, future_end,
                       "legitimate: signed contracts can end in the future"))

    concession_key = ["hUnit", "sChargeCode", "sDateFrom", "sDateTo"]
    key_dupes = int(concessions_raw.duplicated(concession_key, keep=False).sum())
    rows.append(_check("concessions: rows sharing unit+code+dates (kept, flagged)", True, key_dupes))
    positive_amounts = int((concessions_raw["sAmount"] > 0).sum())
    rows.append(_check("concessions: amounts are credits (≤ 0)", positive_amounts == 0, positive_amounts))

    asking_dupes = int(asking_raw.duplicated(["hUnit", "sMonth"]).sum())
    rows.append(_check("asking: no duplicate unit + month", asking_dupes == 0, asking_dupes))
    snapshot_months = listings["sAsOf"].nunique()
    rows.append(_check("listings: distinct sAsOf snapshot months", True, int(snapshot_months),
                       "listing prices are not one uniform snapshot"))

    return pd.DataFrame(rows)
