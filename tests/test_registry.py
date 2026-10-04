"""Tests for the external-source registry (market.registry) and the extraction helpers. Owner: MSR.

Hand-made public-style observations only; no network calls and no CRM data.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pandas as pd
import pytest

from leaselens.config import load_config, repo_root
from leaselens.contracts import EXTERNAL_COLUMNS, MONTHS_PER_YEAR, PERCENT
from leaselens.market.registry import as_of, load_external, validate_external

CUTOFF = pd.Timestamp("2022-12-31")
ONE_DAY = pd.Timedelta(days=1)


def load_script():
    path = repo_root() / "scripts" / "extract_sources.py"
    spec = importlib.util.spec_from_file_location("extract_sources", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def observation(**overrides) -> dict:
    row = {
        "series_id": "test_rent_cpi_qc", "publisher": "Test Publisher", "geography": "QC", "metric": "rent_cpi",
        "unit": "pct", "ref_period_start": "2021-01-01", "ref_period_end": "2021-12-31", "value": "2.5",
        "release_date": "2022-01-19", "url": "https://example.org/table", "location_in_source": "Table 1",
        "accessed_date": "2026-10-03", "extracted_by": "manual", "verified_by": "tester", "notes": "",
    }
    return {**row, **overrides}


def write_csv(rows: list[dict], path: Path) -> Path:
    pd.DataFrame(rows, columns=EXTERNAL_COLUMNS).to_csv(path, index=False)
    return path


@pytest.fixture
def external(tmp_path) -> pd.DataFrame:
    rows = [
        observation(series_id="before", release_date="2022-06-01"),
        observation(series_id="on_cutoff", release_date=CUTOFF.strftime("%Y-%m-%d")),
        observation(series_id="after", ref_period_start="2022-01-01", ref_period_end="2022-12-31",
                    release_date="2023-01-17"),
    ]
    return load_external(write_csv(rows, tmp_path / "sources.csv"))


# ---------------------------------------------------------------------------
# load_external
# ---------------------------------------------------------------------------
def test_load_external_returns_contract_columns_and_types(external):
    assert list(external.columns) == EXTERNAL_COLUMNS
    for column in ["ref_period_start", "ref_period_end", "release_date", "accessed_date"]:
        assert pd.api.types.is_datetime64_any_dtype(external[column])
    assert external["value"].dtype == float


def test_load_external_rejects_missing_column(tmp_path):
    path = tmp_path / "sources.csv"
    pd.DataFrame([observation()]).drop(columns="release_date").to_csv(path, index=False)
    with pytest.raises(ValueError, match="release_date"):
        load_external(path)


def test_load_external_rejects_row_without_release_date(tmp_path):
    with pytest.raises(ValueError, match="release_date"):
        load_external(write_csv([observation(release_date="")], tmp_path / "sources.csv"))


def test_committed_sources_file_loads_and_validates():
    cfg = load_config(mode="synthetic")
    path = Path(cfg["_root"]) / cfg["data"]["public_dir"] / cfg["external"]["sources_file"]
    assert validate_external(load_external(path), cfg) == []


# ---------------------------------------------------------------------------
# as_of: the leakage gate
# ---------------------------------------------------------------------------
def test_as_of_rejects_post_cutoff_rows(external):
    kept = as_of(external, CUTOFF)
    assert "after" not in set(kept["series_id"])
    assert (kept["release_date"] <= CUTOFF).all()


def test_as_of_cutoff_day_is_inclusive(external):
    assert set(as_of(external, CUTOFF)["series_id"]) == {"before", "on_cutoff"}
    assert set(as_of(external, CUTOFF - ONE_DAY)["series_id"]) == {"before"}


def test_as_of_uses_release_date_not_reference_period(tmp_path):
    """A 2021 value first published after the cutoff is still unknown at the cutoff."""
    late = load_external(write_csv([observation(release_date="2023-02-01")], tmp_path / "sources.csv"))
    assert late["ref_period_end"].iloc[0] < CUTOFF
    assert as_of(late, CUTOFF).empty


def test_as_of_does_not_modify_input(external):
    before = external.copy()
    as_of(external, CUTOFF)
    pd.testing.assert_frame_equal(external, before)


# ---------------------------------------------------------------------------
# validate_external
# ---------------------------------------------------------------------------
def test_validate_accepts_clean_table(external, cfg):
    assert validate_external(external, cfg) == []


@pytest.mark.parametrize("overrides, expected", [
    ({"metric": "occupancy_rate"}, "unknown metric"),
    ({"extracted_by": "guess"}, "unknown extracted_by"),
    ({"verified_by": ""}, "without verified_by"),
    ({"url": ""}, "without url"),
    ({"release_date": "2020-06-01"}, "released before"),
])
def test_validate_flags_bad_rows(tmp_path, cfg, overrides, expected):
    table = load_external(write_csv([observation(**overrides)], tmp_path / "sources.csv"))
    assert any(expected in problem for problem in validate_external(table, cfg))


def test_validate_allows_announced_ahead_metrics(tmp_path, cfg):
    """A guideline published before the year it applies to is valid; the same dates on rent CPI are not."""
    assert "ontario_guideline_pct" in cfg["external"]["announced_ahead_metrics"]
    ahead = observation(metric="ontario_guideline_pct", release_date="2020-08-31")
    assert validate_external(load_external(write_csv([ahead], tmp_path / "ahead.csv")), cfg) == []
    early = observation(release_date="2020-08-31")
    problems = validate_external(load_external(write_csv([early], tmp_path / "early.csv")), cfg)
    assert any("released before" in problem for problem in problems)


def test_validate_flags_duplicate_observations(tmp_path, cfg):
    table = load_external(write_csv([observation(), observation(value="9.9")], tmp_path / "sources.csv"))
    assert any("duplicate" in problem for problem in validate_external(table, cfg))


# ---------------------------------------------------------------------------
# Extraction helpers (scripts/extract_sources.py), offline
# ---------------------------------------------------------------------------
def monthly_points(year_values: dict[int, float], release: str) -> list[dict]:
    return [{"refPer": f"{year}-{month:02d}-01", "value": value, "releaseTime": release}
            for year, value in year_values.items() for month in range(1, MONTHS_PER_YEAR + 1)]


def test_annual_average_change_from_monthly_index(cfg):
    script = load_script()
    first = cfg["external"]["statcan"]["first_year"]
    points = monthly_points({first: 100.0, first + 1: 104.0}, "2020-01-20T08:30")
    points[-1]["releaseTime"] = "2021-02-16T08:30"  # last input released later → annual row dated then
    monthly = script.statcan_monthly_rows(points, "QC", 1, cfg, "2026-10-03")
    annual = script.annual_average_change(monthly)
    assert len(annual) == 1
    row = annual.iloc[0]
    assert row["metric"] == "rent_cpi" and row["geography"] == "QC"
    assert row["value"] == pytest.approx(PERCENT * (104.0 / 100.0 - 1))
    assert row["ref_period_start"] == pd.Timestamp(f"{first + 1}-01-01")
    assert row["ref_period_end"] == pd.Timestamp(f"{first + 1}-12-31")
    assert row["release_date"] == pd.Timestamp("2021-02-16")


def test_annual_average_change_skips_incomplete_years(cfg):
    script = load_script()
    first = cfg["external"]["statcan"]["first_year"]
    points = monthly_points({first: 100.0, first + 1: 104.0}, "2020-01-20T08:30")[:-1]
    monthly = script.statcan_monthly_rows(points, "ON", 1, cfg, "2026-10-03")
    assert script.annual_average_change(monthly).empty


def test_series_id_is_clean_snake_case():
    script = load_script()
    assert script.series_id("cmhc", "Montreal CMA", "Non-turnover (2-bed)", "") == "cmhc_montreal_cma_non_turnover_2_bed"


def test_promote_copies_only_verified_rows(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(repo_root() / "config", root / "config")
    cfg = load_config(root=root, mode="synthetic")
    public = root / cfg["data"]["public_dir"]
    public.mkdir(parents=True)
    write_csv([], public / cfg["external"]["sources_file"])
    write_csv([observation(series_id="checked"),
               observation(series_id="unchecked", verified_by="", release_date="")],
              public / cfg["external"]["draft_file"])
    assert load_script().promote(cfg) == 1
    promoted = load_external(public / cfg["external"]["sources_file"])
    assert list(promoted["series_id"]) == ["checked"]
    assert validate_external(promoted, cfg) == []
