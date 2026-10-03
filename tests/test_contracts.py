"""Contract sanity checks. Owner: INT."""

from leaselens import contracts


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
