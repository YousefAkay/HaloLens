"""Data dictionary v2: evidence-based renaming of source columns. Owner: INT.

Original names are kept in COLUMN_MAPS so notebook section 02 can show source → canonical.
"""

from __future__ import annotations

import pandas as pd

from leaselens.contracts import (
    ASKING_COLUMNS,
    CONCESSIONS_COLUMNS,
    LEASES_COLUMNS,
    LUMP_CHARGE_CODES,
    PROVINCE_CODES,
    UNITS_COLUMNS,
    CanonicalTables,
)

LEASE_MAP = {
    "hUnit": "unit_id", "sPropCode": "prop_code", "sUnitCode": "unit_code",
    "sBuilding": "building", "sState": "province", "sCity": "city",
    "sBeds": "beds", "sBaths": "baths", "sSqft": "sqft", "sFloor": "floor", "sUnitType": "unit_type",
    "sTermSeq": "lease_seq", "sRenewal": "is_renewal",
    "sSignDate": "sign_date", "sLeaseFrom": "lease_start", "sLeaseTo": "lease_end",
    "sTermMonths": "term_months_daycount", "sLeaseTerm": "term_label",
    "sRent": "rent_contract", "sRentEffective": "rent_net_all_incentives", "sConcession": "has_concession",
}

CONCESSION_MAP = {
    "hUnit": "unit_id", "sPropCode": "prop_code", "sUnitCode": "unit_code",
    "sBuilding": "building", "sState": "province",
    "sChargeCode": "charge_code", "sChargeDesc": "charge_desc",
    "sDateFrom": "date_from", "sDateTo": "date_to", "sMonths": "months",
}

ASKING_MAP = {
    "hUnit": "unit_id", "sPropCode": "prop_code", "sUnitCode": "unit_code",
    "sBuilding": "building", "sState": "province", "sBeds": "beds", "sSqft": "sqft",
    "sMonth": "month", "sAskingRent": "asking_rent",
}

UNIT_MAP = {
    "hUnit": "unit_id", "sPropCode": "prop_code", "sUnitCode": "unit_code",
    "sBuilding": "building", "sState": "province", "sCity": "city",
    "sBeds": "beds", "sBaths": "baths", "sSqft": "sqft", "sFloor": "floor", "sUnitType": "unit_type",
    "sRent": "listing_asking_rent", "sAsOf": "snapshot_month", "sAvailable": "available_date",
}

COLUMN_MAPS = {"leases": LEASE_MAP, "concessions": CONCESSION_MAP, "asking": ASKING_MAP, "listings": UNIT_MAP}

# Source columns intentionally dropped, with the evidence (shown in notebook section 02)
DROPPED_COLUMNS = {
    "leases": {"sAvailable": "identical to sLeaseFrom on every row (checked in io.qa)"},
}


def column_mapping() -> pd.DataFrame:
    """Source → canonical mapping as a table, for documentation."""
    rows = [
        {"table": table, "source_column": source, "canonical_column": canonical}
        for table, mapping in COLUMN_MAPS.items()
        for source, canonical in mapping.items()
    ]
    rows += [
        {"table": table, "source_column": source, "canonical_column": f"(dropped: {reason})"}
        for table, dropped in DROPPED_COLUMNS.items()
        for source, reason in dropped.items()
    ]
    return pd.DataFrame(rows)


def _province(series: pd.Series) -> pd.Series:
    mapped = series.map(PROVINCE_CODES)
    if mapped.isna().any():
        unknown = sorted(series[mapped.isna()].unique())
        raise ValueError(f"Unknown province values: {unknown}")
    return mapped


def _leases(raw: pd.DataFrame) -> pd.DataFrame:
    available_matches_start = (raw["sAvailable"] == raw["sLeaseFrom"]).all()
    if not available_matches_start:
        raise ValueError("sAvailable differs from sLeaseFrom; revisit DROPPED_COLUMNS before dropping it")
    df = raw.rename(columns=LEASE_MAP)
    for column in ["sign_date", "lease_start", "lease_end"]:
        df[column] = pd.to_datetime(df[column])
    df["province"] = _province(df["province"])
    df["is_renewal"] = df["is_renewal"].astype(int).astype(bool)
    df["has_concession"] = df["has_concession"].astype(int).astype(bool)
    df["lease_seq"] = df["lease_seq"].astype(int)
    df["beds"] = df["beds"].astype(int)
    return df[LEASES_COLUMNS].reset_index(drop=True)


def _concessions(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=CONCESSION_MAP).reset_index(drop=True)
    df["concession_id"] = df.index.astype(int)
    df["credit_amount"] = -raw["sAmount"].to_numpy()  # source amounts are negative credits
    for column in ["date_from", "date_to"]:
        df[column] = pd.to_datetime(df[column])
    df["province"] = _province(df["province"])
    df["credit_kind"] = df["charge_code"].map(lambda code: "lump" if code in LUMP_CHARGE_CODES else "monthly")
    return df[CONCESSIONS_COLUMNS]


def _asking(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=ASKING_MAP)
    df["month"] = pd.PeriodIndex(df["month"], freq="M")
    df["province"] = _province(df["province"])
    df["beds"] = df["beds"].astype(int)
    return df[ASKING_COLUMNS].reset_index(drop=True)


def _units(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=UNIT_MAP)
    df["snapshot_month"] = pd.PeriodIndex(df["snapshot_month"], freq="M")
    df["available_date"] = pd.to_datetime(df["available_date"])
    df["province"] = _province(df["province"])
    df["beds"] = df["beds"].astype(int)
    return df[UNITS_COLUMNS].reset_index(drop=True)


def canonicalize(raw: dict[str, pd.DataFrame]) -> CanonicalTables:
    """Rename, type and lightly derive the four tables. Pure function: `raw` is not modified."""
    return CanonicalTables(
        leases=_leases(raw["leases"].copy()),
        concessions=_concessions(raw["concessions"].copy()),
        asking=_asking(raw["asking"].copy()),
        units=_units(raw["listings"].copy()),
    )
