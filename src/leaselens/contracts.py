"""Shared contracts: canonical column names, table schemas, dataclasses and constants.

Owner: INT. FROZEN after H1. Changes only through a change request to INT (AGENTS.md Section 6.4).
Every track implements its functions against these names and signatures (AGENTS.md Section 7).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# ---------------------------------------------------------------------------
# Named constants (the only numeric literals allowed outside config files)
# ---------------------------------------------------------------------------
DAYS_PER_YEAR = 365.25
MONTHS_PER_YEAR = 12
PERCENT = 100

# Consistent chart colors (Okabe-Ito, colorblind-safe). Contractual vs net never swap colors.
COLOR_CONTRACT = "#0072B2"  # blue
COLOR_NET = "#E69F00"       # orange
COLOR_NAIVE = "#999999"     # grey
COLOR_MARKET = "#009E73"    # green

PROVINCE_CODES = {"Quebec": "QC", "Ontario": "ON"}

# Source tables in the sponsor package (file name → logical name)
SOURCE_FILES = {
    "listings": "listings.csv",
    "leases": "lease_history.csv",
    "concessions": "concessions.csv",
    "asking": "asking_history.csv",
}

# Identifier columns that must be read as strings (leading zeros in unit codes)
SOURCE_ID_COLUMNS = ["hProperty", "hUnit", "hBuilding", "sPropCode", "sUnitCode"]

# Concession codes. PromoPay is a one-off credit; all others are monthly amounts repeated over sMonths.
LUMP_CHARGE_CODES = {"PromoPay"}
ACCESSORY_CHARGE_CODES = {"freepark", "freelock", "freeappl"}
RENT_CHARGE_CODES = {"freerent", "PromoPay"}
OTHER_CHARGE_CODES = {"Freeothe", "Indem", "Referenc"}

# ---------------------------------------------------------------------------
# Canonical schemas (column order is part of the contract)
# ---------------------------------------------------------------------------
LEASES_COLUMNS = [
    "unit_id", "prop_code", "unit_code", "building", "province", "city",
    "beds", "baths", "sqft", "floor", "unit_type",
    "lease_seq", "is_renewal", "sign_date", "lease_start", "lease_end",
    "term_months_daycount", "term_label",
    "rent_contract", "rent_net_all_incentives", "has_concession",
]

CONCESSIONS_COLUMNS = [
    "concession_id", "unit_id", "prop_code", "unit_code", "building", "province",
    "charge_code", "charge_desc", "credit_amount", "date_from", "date_to", "months", "credit_kind",
]

ASKING_COLUMNS = [
    "unit_id", "prop_code", "unit_code", "building", "province", "beds", "sqft", "month", "asking_rent",
]

UNITS_COLUMNS = [
    "unit_id", "prop_code", "unit_code", "building", "province", "city", "beds", "baths", "sqft",
    "floor", "unit_type", "listing_asking_rent", "snapshot_month", "available_date",
]

PAIRS_COLUMNS = [
    "unit_id", "prop_code", "building", "province", "beds", "is_renewal",
    "prev_lease_start", "lease_start", "sign_date", "year", "gap_years",
    "rent_contract_prev", "rent_contract", "rent_net_prev", "rent_net",
    "loggrowth_contract", "loggrowth_net", "eligible", "exclusion_reason",
]

LINKS_COLUMNS = [
    "concession_id", "unit_id", "lease_start", "n_candidates", "rule", "status", "recon_error",
]
LINK_STATUSES = ("unique", "resolved_by_fit", "unresolved")

EXTERNAL_COLUMNS = [
    "series_id", "publisher", "geography", "metric", "unit",
    "ref_period_start", "ref_period_end", "value", "release_date", "url",
    "location_in_source", "accessed_date", "extracted_by", "verified_by", "notes",
]

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class CanonicalTables:
    """The four sponsor tables after renaming and typing (io.dictionary.canonicalize)."""

    leases: pd.DataFrame
    concessions: pd.DataFrame
    asking: pd.DataFrame
    units: pd.DataFrame


@dataclass
class Snapshot:
    """Everything knowable at `cutoff` (forecast.asof.make_snapshot). No later information inside."""

    cutoff: pd.Timestamp
    leases: pd.DataFrame
    concessions: pd.DataFrame
    asking: pd.DataFrame
    units: pd.DataFrame | None
    external: pd.DataFrame


@dataclass
class ForecastResult:
    """Output of forecast.combine.forecast. Percentages are in percent (e.g. 3.2 means 3.2%)."""

    target_year: int
    cutoff: pd.Timestamp
    headline_net_pct: float
    headline_contract_pct: float
    median_net_pct: float
    median_contract_pct: float
    segments: pd.DataFrame
    components: dict = field(default_factory=dict)
    model_name: str = ""
    assumptions: list[str] = field(default_factory=list)


@dataclass
class BacktestResult:
    """Output of evaluate.backtest.run_backtest. Errors in percentage points (forecast − actual)."""

    target_year: int
    forecast: ForecastResult
    actual_net_pct: float
    actual_contract_pct: float
    error_pp_net: float
    error_pp_contract: float
    coverage: dict = field(default_factory=dict)
