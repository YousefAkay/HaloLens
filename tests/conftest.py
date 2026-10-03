"""Shared pytest fixtures. Owner: INT.

All fixtures use the committed synthetic data (data/synthetic). Tests never read CRM files.
Regenerate fixtures with: python scripts/make_synthetic.py
"""

from __future__ import annotations

import pytest

from leaselens.config import data_dir, load_config
from leaselens.io import canonicalize, load_raw


@pytest.fixture(scope="session")
def cfg() -> dict:
    """Merged configuration forced to synthetic mode."""
    return load_config(mode="synthetic")


@pytest.fixture(scope="session")
def raw(cfg) -> dict:
    """Synthetic source tables with original column names (hashes verified)."""
    return load_raw(data_dir(cfg))


@pytest.fixture(scope="session")
def tables(raw):
    """Synthetic CanonicalTables."""
    return canonicalize(raw)
