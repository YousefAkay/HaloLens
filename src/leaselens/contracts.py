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


# ---------------------------------------------------------------------------
# Aggregates JSON (I-09a). The only file the Streamlit app and the LLM narrative may read (AGENTS.md Section 15).
# Percentages are in percent units (3.2 means 3.2%). null means "not computable", never a placeholder.
# Every object is closed (additionalProperties false): no unit-level list, identifier or extra field can appear.
# ---------------------------------------------------------------------------
AGGREGATES_SCHEMA_VERSION = 1
INFORMATION_RULES = ("jan31", "dec31_strict")  # jan31: public data by January 31 of the target year; dec31_strict: sensitivity
MODES = ("synthetic", "real")
LEVER_LABELS = ("minus", "zero", "plus", "none")  # scenario lever settings: minus or plus one step, zero, or not a lever
MET_LABELS = ("exempt", "guideline", "none")  # Met central (exempt) or alternative (guideline applies), or not a lever

_NUMBER = {"type": ["number", "null"]}
_COUNT = {"type": "integer", "minimum": 0}
_DATE = {"type": "string", "format": "date"}
_TEXT = {"type": "string"}

AGGREGATES_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "leaselens-aggregates",
    "title": "LeaseLens aggregates (counts and percentages only)",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "mode", "target_year", "as_of", "definition", "headline", "companions",
                 "backtest", "coverage", "scenarios", "sources", "scenario_grid", "building_beds", "sensitivity",
                 "note"],
    "properties": {
        "schema_version": {"const": AGGREGATES_SCHEMA_VERSION},
        "mode": {"enum": list(MODES)},
        "target_year": {"type": "integer"},
        "as_of": {
            "type": "object", "additionalProperties": False,
            "required": ["crm_cutoff", "external_cutoff", "external_strict_cutoff"],
            "properties": {"crm_cutoff": _DATE, "external_cutoff": _DATE, "external_strict_cutoff": _DATE},
        },
        "definition": _TEXT,
        "headline": {
            "type": "object", "additionalProperties": False,
            "required": ["net_pct", "contract_pct", "information_rule", "model", "model_range", "provinces"],
            "properties": {
                "net_pct": _NUMBER, "contract_pct": _NUMBER,
                "information_rule": {"enum": list(INFORMATION_RULES)},
                # the pre-declared champion (I-09 wires this to F-08's champion_forecast)
                "model": {"type": ["string", "null"]},
                # low and high 2026 net headline across the candidate models (B0, B1, E1, E2)
                "model_range": {
                    "type": "object", "additionalProperties": False,
                    "required": ["low_net_pct", "high_net_pct"],
                    "properties": {"low_net_pct": _NUMBER, "high_net_pct": _NUMBER},
                },
                # headline split by province (never cross-applied: QC under the TAL, ON under the guideline)
                "provinces": {
                    "type": "object", "additionalProperties": False,
                    "required": ["QC", "ON"],
                    "properties": {
                        province: {
                            "type": "object", "additionalProperties": False,
                            "required": ["net_pct", "contract_pct"],
                            "properties": {"net_pct": _NUMBER, "contract_pct": _NUMBER},
                        } for province in ("QC", "ON")
                    },
                },
            },
        },
        "companions": {
            "type": "object", "additionalProperties": False,
            "required": ["median_net_pct", "median_contract_pct"],
            "properties": {"median_net_pct": _NUMBER, "median_contract_pct": _NUMBER},
        },
        "backtest": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["year", "model", "information_rule", "forecast_net_pct", "actual_net_pct",
                             "error_pp_net", "forecast_contract_pct", "actual_contract_pct", "error_pp_contract"],
                "properties": {
                    "year": {"type": "integer"}, "model": _TEXT,
                    "information_rule": {"enum": list(INFORMATION_RULES)},
                    "forecast_net_pct": _NUMBER, "actual_net_pct": _NUMBER, "error_pp_net": _NUMBER,
                    "forecast_contract_pct": _NUMBER, "actual_contract_pct": _NUMBER, "error_pp_contract": _NUMBER,
                },
            },
        },
        "coverage": {
            "type": "object", "additionalProperties": False,
            "required": ["leases", "units", "eligible_pairs", "excluded_pairs", "segments",
                         "concessions", "asking_rows", "external_rows"],
            "properties": {"leases": _COUNT, "units": _COUNT, "eligible_pairs": _COUNT,
                           "excluded_pairs": _COUNT, "segments": _COUNT, "concessions": _COUNT,
                           "asking_rows": _COUNT, "external_rows": _COUNT},
        },
        "scenarios": {
            "type": "object", "additionalProperties": False,
            "required": ["low_net_pct", "central_net_pct", "high_net_pct"],
            "properties": {"low_net_pct": _NUMBER, "central_net_pct": _NUMBER, "high_net_pct": _NUMBER},
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["series_id", "publisher", "release_date", "url"],
                "properties": {"series_id": _TEXT, "publisher": _TEXT, "release_date": _DATE, "url": _TEXT},
            },
        },
        # Scenario grid (I-12): E2 under every lever combination and both information rules, plus the champion's
        # base headline per rule (its levers are "none": scenario levers act on the E2 segments only).
        "scenario_grid": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["model", "information_rule", "incentive_shift", "renewal_shift", "met_regime",
                             "headline_net_pct", "headline_contract_pct"],
                "properties": {
                    "model": _TEXT, "information_rule": {"enum": list(INFORMATION_RULES)},
                    "incentive_shift": {"enum": list(LEVER_LABELS)}, "renewal_shift": {"enum": list(LEVER_LABELS)},
                    "met_regime": {"enum": list(MET_LABELS)},
                    "headline_net_pct": _NUMBER, "headline_contract_pct": _NUMBER,
                },
            },
        },
        # Building x beds (I-12): forecast per building and bedroom count; building names only, never unit identifiers.
        "building_beds": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["building", "beds", "n_pairs", "net_pct_raw", "net_pct_shrunk", "contract_pct_raw",
                             "contract_pct_shrunk"],
                "properties": {
                    "building": _TEXT, "beds": {"type": "integer"}, "n_pairs": _COUNT,
                    "net_pct_raw": _NUMBER, "net_pct_shrunk": _NUMBER,
                    "contract_pct_raw": _NUMBER, "contract_pct_shrunk": _NUMBER,
                },
            },
        },
        # One-assumption-at-a-time sensitivities (F-10): deltas are relative to the base of the same model.
        "sensitivity": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["assumption", "variant", "setting", "model", "headline_net_pct", "base_net_pct",
                             "delta_pp", "note"],
                "properties": {
                    "assumption": _TEXT, "variant": _TEXT, "setting": _TEXT, "model": _TEXT,
                    "headline_net_pct": _NUMBER, "base_net_pct": _NUMBER, "delta_pp": _NUMBER, "note": _TEXT,
                },
            },
        },
        "note": _TEXT,
    },
}
