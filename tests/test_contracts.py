"""Contract sanity checks and config helpers. Owner: INT."""

import pandas as pd

from leaselens import contracts
from leaselens.config import cutoff_for, external_cutoff_for, load_config


def test_schema_columns_are_unique():
    for name in dir(contracts):
        if name.endswith("_COLUMNS") and isinstance(getattr(contracts, name), list):
            columns = getattr(contracts, name)
            assert len(columns) == len(set(columns)), name


def test_canonical_tables_match_schemas(tables):
    assert list(tables.leases.columns) == contracts.LEASES_COLUMNS
    assert list(tables.concessions.columns) == contracts.CONCESSIONS_COLUMNS
    assert list(tables.asking.columns) == contracts.ASKING_COLUMNS
    assert list(tables.units.columns) == contracts.UNITS_COLUMNS


def test_charge_code_groups_do_not_overlap_except_promopay():
    assert contracts.ACCESSORY_CHARGE_CODES.isdisjoint(contracts.RENT_CHARGE_CODES)
    assert contracts.LUMP_CHARGE_CODES <= contracts.RENT_CHARGE_CODES


def test_external_cutoff_is_january_31_of_the_target_year():
    cfg = load_config(mode="synthetic")
    assert external_cutoff_for(2026, cfg) == pd.Timestamp("2026-01-31")
    assert external_cutoff_for(2023, cfg) == pd.Timestamp("2023-01-31")


def test_crm_cutoff_is_unchanged_by_the_external_cutoff():
    cfg = load_config(mode="synthetic")
    assert cutoff_for(2026, cfg) == pd.Timestamp("2025-12-31")
    assert external_cutoff_for(2026, cfg) > cutoff_for(2026, cfg)


def test_strict_sensitivity_flag_is_configured():
    cfg = load_config(mode="synthetic")
    assert cfg["forecast_years"]["external_cutoff_strict_sensitivity"] is True
