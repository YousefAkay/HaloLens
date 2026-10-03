"""Tests for scripts/smoke_real_data.py. Owner: INT.

Synthetic fixtures only: the real-data path is never exercised by tests (AGENTS.md §3.2).
"""

from __future__ import annotations

import importlib.util

import pandas as pd

from leaselens.config import repo_root
from leaselens.measure.pairs import REASON_SEPARATOR

_spec = importlib.util.spec_from_file_location("smoke_real_data", repo_root() / "scripts" / "smoke_real_data.py")
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)


def test_exclusion_counts_count_every_reason_of_a_pair():
    pairs = pd.DataFrame({
        "eligible": [True, False, False],
        "exclusion_reason": ["", f"gap_too_short{REASON_SEPARATOR}non_positive_rent", "gap_too_short"],
    })
    counts = smoke.exclusion_counts(pairs)
    assert counts == {"gap_too_short": 2, "non_positive_rent": 1}


def test_empty_external_has_contract_columns_and_no_rows():
    external = smoke.empty_external()
    assert len(external) == 0
    assert "release_date" in external.columns
    assert pd.api.types.is_datetime64_any_dtype(external["release_date"])


def test_synthetic_smoke_run_succeeds_and_prints_counts_only(capsys):
    assert smoke.main(["--synthetic"]) == smoke.EXIT_OK
    output = capsys.readouterr().out
    assert "Snapshot at cutoff" in output
    assert "hUnit" not in output and "sPropCode" not in output
