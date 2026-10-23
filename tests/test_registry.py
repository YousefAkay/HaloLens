"""Tests for the external-source registry (market.registry), the extraction helpers and the market reconciliation
(market.reconcile_market). Owner: MSR.

Hand-made public-style observations only; no network calls and no CRM data.
"""

from __future__ import annotations

import copy
import importlib.util
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from halolens.config import external_cutoff_for, load_config, repo_root
from halolens.contracts import EXTERNAL_COLUMNS, MONTHS_PER_YEAR, PAIRS_COLUMNS, PERCENT
from halolens.market.reconcile_market import (PROVENANCE_COLUMNS, RECONCILE_COLUMNS, SUMMARY_COLUMNS, provenance_table,
                                              reconcile, reconcile_summary)
from halolens.market.registry import (WATCH_STATUSES, as_of, load_external, load_watch, parse_external, validate_external,
                                       watch_status, watch_summary)

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


# ---------------------------------------------------------------------------
# Source watcher (--watch)
# ---------------------------------------------------------------------------
def test_watch_rows_keeps_unknown_periods_and_tags_status():
    script = load_script()
    sources = parse_external(pd.DataFrame([observation(series_id="cpi", release_date="2022-01-19")]))
    candidates = pd.DataFrame([
        observation(series_id="cpi", release_date="2022-01-19"),  # already known period → dropped
        observation(series_id="cpi", ref_period_start="2022-01-01", ref_period_end="2022-12-31",
                    release_date="2023-01-17"),
        observation(series_id="cpi", ref_period_start="2020-01-01", ref_period_end="2020-12-31",
                    release_date="2021-01-19"),
        observation(series_id="brand_new", release_date="2020-01-01"),
        observation(series_id="undated", release_date=""),
    ], columns=EXTERNAL_COLUMNS)
    watched = script.watch_rows(candidates, sources)
    assert list(watched.columns) == EXTERNAL_COLUMNS
    status = dict(zip(watched["series_id"] + "@" + watched["ref_period_start"],
                      watched["notes"].str.extract(r"\[watch: (\w+)\]")[0]))
    assert status == {"brand_new@2021-01-01": "new_release", "cpi@2020-01-01": "missing_period",
                      "cpi@2022-01-01": "new_release", "undated@2021-01-01": "release_date_unknown"}


def test_new_since_cutoff_lists_only_series_released_after_cutoff():
    script = load_script()
    watched = script.as_csv_text(pd.DataFrame([
        observation(series_id="late", ref_period_start="2025-01-01", ref_period_end="2025-12-31",
                    release_date="2026-03-01"),
        observation(series_id="late", ref_period_start="2026-01-01", ref_period_end="2026-12-31",
                    release_date="2026-04-01"),
        observation(series_id="on_time", release_date="2026-01-31"),
        observation(series_id="undated", release_date=""),
        observation(series_id="undated", ref_period_start="2027-01-01", ref_period_end="2027-12-31",
                    release_date=""),
    ], columns=EXTERNAL_COLUMNS))
    late, undated = script.new_since_cutoff(watched, pd.Timestamp("2026-01-31"))
    assert late.to_dict("records") == [{"series_id": "late", "rows": 2, "first_period": "2025-01-01",
                                        "last_period": "2026-12-31", "latest_release": "2026-04-01"}]
    assert undated.to_dict("records") == [{"series_id": "undated", "rows": 1, "first_period": "2027-01-01",
                                           "last_period": "2027-12-31", "latest_release": ""}]


def test_watch_summary_counts_status_and_rows_after_cutoff(tmp_path):
    script = load_script()
    candidates = pd.DataFrame([
        observation(series_id="late", ref_period_start="2026-01-01", ref_period_end="2026-12-31",
                    release_date="2026-04-01"),
        observation(series_id="old", ref_period_start="2020-01-01", ref_period_end="2020-12-31",
                    release_date="2021-01-19"),
        observation(series_id="undated_future", ref_period_start="2027-01-01", ref_period_end="2027-12-31",
                    release_date=""),
        observation(series_id="undated_past", release_date=""),
    ], columns=EXTERNAL_COLUMNS)
    sources = parse_external(pd.DataFrame([observation(series_id="old", release_date="2022-01-19")]))
    path = tmp_path / "sources_watch.csv"
    script.watch_rows(candidates, sources).to_csv(path, index=False)
    watch = load_watch(path)
    assert list(watch.columns) == EXTERNAL_COLUMNS
    summary = watch_summary(watch, pd.Timestamp("2026-01-31"))
    assert summary == {"n_rows": 4, "by_status": {"new_release": 1, "missing_period": 1, "release_date_unknown": 2},
                       "n_after_cutoff": 2}


def test_load_watch_missing_file_is_empty(tmp_path):
    watch = load_watch(tmp_path / "absent.csv")
    assert watch.empty and list(watch.columns) == EXTERNAL_COLUMNS
    assert watch_summary(watch, pd.Timestamp("2026-01-31"))["n_rows"] == 0


def test_committed_watch_file_has_known_statuses(cfg):
    path = repo_root() / cfg["data"]["public_dir"] / cfg["external"]["watch_file"]
    watch = load_watch(path)
    assert set(watch_status(watch)) <= set(WATCH_STATUSES)


def test_watch_without_key_skips_pages_and_never_touches_cache(tmp_path, monkeypatch, capsys):
    script = load_script()
    root = tmp_path / "repo"
    shutil.copytree(repo_root() / "config", root / "config")
    cfg = load_config(root=root, mode="synthetic")
    public = root / cfg["data"]["public_dir"]
    public.mkdir(parents=True)
    write_csv([observation()], public / cfg["external"]["sources_file"])
    cache_dir = public / cfg["external"]["cache_dir"]
    cache_dir.mkdir()
    (cache_dir / f"{cfg['external']['pages'][0]['source_id']}.json").write_text("{}", encoding="utf-8")

    def no_network(*args, **kwargs):
        raise OSError("offline test")

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(script, "statcan_post", no_network)
    monkeypatch.setattr(script, "page_text", no_network)
    watched = script.watch(cfg)
    out = capsys.readouterr().out
    assert watched.empty
    assert "no ANTHROPIC_API_KEY" in out and "new since cutoff" in out
    assert list(pd.read_csv(public / cfg["external"]["watch_file"]).columns) == EXTERNAL_COLUMNS
    assert (cache_dir / f"{cfg['external']['pages'][0]['source_id']}.json").read_text(encoding="utf-8") == "{}"


def test_watch_flag_and_step_are_exclusive():
    script = load_script()
    with pytest.raises(SystemExit):
        script.main(["statcan", "--watch"])
    with pytest.raises(SystemExit):
        script.main([])


# ---------------------------------------------------------------------------
# reconcile_market: internal same-unit growth vs public series
# ---------------------------------------------------------------------------
RECONCILE_YEAR = 2024
INTERNAL_GROWTH = 0.05
MARKET_PCT = 3.0
NET_DISCOUNT = 0.01
BASE_RENT = 1000.0


def growth_pair(unit: str, province: str, renewal: bool = True, beds: int = 2, growth: float = INTERNAL_GROWTH,
                year: int = RECONCILE_YEAR) -> dict:
    """One eligible annual pair with the given contractual log growth (hand-made, no CRM data)."""
    start = pd.Timestamp(f"{year}-07-01")
    row = {
        "unit_id": unit, "prop_code": "aaa", "building": "Test", "province": province, "beds": beds,
        "is_renewal": renewal, "prev_lease_start": start - pd.DateOffset(years=1), "lease_start": start,
        "sign_date": start - pd.Timedelta(days=60), "year": year, "gap_years": 1.0,
        "rent_contract_prev": BASE_RENT, "rent_contract": BASE_RENT * math.exp(growth),
        "rent_net_prev": BASE_RENT, "rent_net": BASE_RENT * math.exp(growth - NET_DISCOUNT),
        "loggrowth_contract": growth, "loggrowth_net": growth - NET_DISCOUNT, "eligible": True, "exclusion_reason": "",
    }
    return {column: row[column] for column in PAIRS_COLUMNS}


def many_pairs(count: int, province: str, prefix: str = "u", **kwargs) -> list[dict]:
    return [growth_pair(f"{prefix}-{province}-{index}", province, **kwargs) for index in range(count)]


def reconcile_cfg(cfg: dict) -> dict:
    """Synthetic config with one all-lease comparison and one 2-bedroom turnover comparison."""
    settings = copy.deepcopy(cfg)
    settings["reconcile_market"]["comparisons"] = [
        {"name": "total", "label": "Total", "lease_type": "all", "beds": None,
         "series": {"QC": "mtl_total", "ON": "ott_total"}},
        {"name": "turnover", "label": "Turnover", "lease_type": "turnover", "beds": 2,
         "series": {"QC": "mtl_turnover", "ON": "ott_turnover"}},
    ]
    return settings


def market_row(series_id: str, geography: str, value: float, release_date: str = "2024-12-17",
               year: int = RECONCILE_YEAR, metric: str = "cmhc_same_sample_rent_growth_pct") -> dict:
    return observation(series_id=series_id, geography=geography, metric=metric, value=str(value),
                       ref_period_start=f"{year}-10-01", ref_period_end=f"{year}-10-31", release_date=release_date)


def market_external(rows: list[dict]) -> pd.DataFrame:
    return parse_external(pd.DataFrame(rows, columns=EXTERNAL_COLUMNS))


def cell(table: pd.DataFrame, comparison: str, province: str) -> pd.Series:
    return table[(table["comparison"] == comparison) & (table["province"] == province)].iloc[0]


def test_reconcile_gap_is_internal_minus_same_province_market(cfg):
    settings = reconcile_cfg(cfg)
    minimum = settings["renewals"]["min_pairs_per_cell"]
    external = market_external([market_row("mtl_total", "Montreal CMA", MARKET_PCT),
                                market_row("ott_total", "Ottawa CMA", MARKET_PCT * 2)])
    table = reconcile(pd.DataFrame(many_pairs(minimum, "QC")), external, settings)
    assert list(table.columns) == RECONCILE_COLUMNS
    quebec = cell(table, "total", "QC")
    expected = PERCENT * (math.exp(INTERNAL_GROWTH) - 1)
    assert quebec["n_pairs"] == minimum
    assert quebec["geography"] == "Montreal CMA"
    assert quebec["internal_contract_pct"] == pytest.approx(expected)
    assert quebec["gap_contract_pp"] == pytest.approx(expected - MARKET_PCT)
    ontario = cell(table, "total", "ON")  # Québec pairs are never compared with Ottawa
    assert ontario["n_pairs"] == 0 and np.isnan(ontario["internal_contract_pct"])


def test_reconcile_thin_cell_keeps_count_without_growth(cfg):
    settings = reconcile_cfg(cfg)
    thin = settings["renewals"]["min_pairs_per_cell"] - 1
    table = reconcile(pd.DataFrame(many_pairs(thin, "QC")),
                      market_external([market_row("mtl_total", "Montreal CMA", MARKET_PCT)]), settings)
    quebec = cell(table, "total", "QC")
    assert quebec["n_pairs"] == thin
    assert np.isnan(quebec["internal_contract_pct"]) and np.isnan(quebec["gap_contract_pp"])


def test_reconcile_filters_lease_type_and_beds(cfg):
    settings = reconcile_cfg(cfg)
    minimum = settings["renewals"]["min_pairs_per_cell"]
    rows = (many_pairs(minimum, "QC", prefix="turnover", renewal=False)
            + many_pairs(minimum, "QC", prefix="renewal", renewal=True)
            + many_pairs(minimum, "QC", prefix="one-bed", renewal=False, beds=1))
    table = reconcile(pd.DataFrame(rows), market_external([market_row("mtl_turnover", "Montreal CMA", MARKET_PCT)]),
                      settings)
    assert cell(table, "turnover", "QC")["n_pairs"] == minimum
    assert cell(table, "total", "QC")["n_pairs"] == len(rows)


def test_reconcile_latest_release_wins_and_next_info_date_flag(cfg):
    settings = reconcile_cfg(cfg)
    revised = MARKET_PCT + 1
    late_release = (external_cutoff_for(RECONCILE_YEAR + 1, settings) + ONE_DAY).strftime("%Y-%m-%d")
    external = market_external([market_row("mtl_total", "Montreal CMA", MARKET_PCT),
                                market_row("mtl_total", "Montreal CMA", revised, release_date=late_release)])
    quebec = cell(reconcile(pd.DataFrame(many_pairs(1, "QC")), external, settings), "total", "QC")
    assert quebec["market_pct"] == revised
    assert not quebec["known_by_next_info_date"]


def test_reconcile_summary_mean_gaps(cfg):
    settings = reconcile_cfg(cfg)
    minimum = settings["renewals"]["min_pairs_per_cell"]
    years = [RECONCILE_YEAR - 1, RECONCILE_YEAR]
    pairs = pd.DataFrame([row for year in years for row in many_pairs(minimum, "QC", prefix=str(year), year=year)])
    external = market_external([market_row("mtl_total", "Montreal CMA", MARKET_PCT, year=year,
                                           release_date=f"{year}-12-17") for year in years])
    summary = reconcile_summary(reconcile(pairs, external, settings))
    assert list(summary.columns) == SUMMARY_COLUMNS
    quebec = cell(summary, "total", "QC")
    assert quebec["n_years"] == len(years)
    assert quebec["mean_gap_contract_pp"] == pytest.approx(PERCENT * (math.exp(INTERNAL_GROWTH) - 1) - MARKET_PCT)


def test_provenance_table_roles(cfg):
    settings = reconcile_cfg(cfg)
    context_metric = settings["reconcile_market"]["context_only_metrics"][0]
    external = market_external([
        market_row("mtl_total", "Montreal CMA", MARKET_PCT),
        market_row("mtl_vacancy", "Montreal CMA", MARKET_PCT, metric=context_metric),
        market_row("tal", "QC", MARKET_PCT, metric="tal_renewal_reference_pct"),
    ])
    table = provenance_table(external, settings)
    assert list(table.columns) == PROVENANCE_COLUMNS
    roles = table.set_index("series_id")["role"]
    assert roles["mtl_total"] == "compared"
    assert roles["mtl_vacancy"] == "context_only"
    assert roles["tal"] == "reference"
    assert table["verified"].all()


def test_committed_reconcile_series_exist_in_sources(cfg):
    series = set(load_external(repo_root() / cfg["data"]["public_dir"] / cfg["external"]["sources_file"])["series_id"])
    for comparison in cfg["reconcile_market"]["comparisons"]:
        assert set(comparison["series"]) == {"QC", "ON"}
        assert set(comparison["series"].values()) <= series


# --- Section 12: references compiled from docs/references.md (measure.labels.track_references_markdown) ---------------

def test_track_references_drops_title_and_boilerplate_and_shifts_headings():
    from halolens.measure.labels import track_references_markdown

    cfg = load_config()["references"]
    boilerplate = "Append one bullet per entry."
    text = (f"# References\n\n{boilerplate} Extra context stays.\n\n## Public data\n- Entry one\n\n\n\n"
            "### Detail\n```\n# not a heading\n```\n")
    body = track_references_markdown(text, boilerplate, cfg["heading_shift"])
    assert "# References" not in body and boilerplate not in body
    assert body.startswith("Extra context stays.")
    assert "#### Public data" in body and "##### Detail" in body
    assert "\n# not a heading\n" in body  # code fence untouched
    assert "\n\n\n" not in body


def test_track_references_empty_file_and_heading_cap():
    from halolens.measure.labels import MAX_HEADING_LEVEL, track_references_markdown

    cfg = load_config()["references"]
    boilerplate = "Append one bullet per entry."
    assert track_references_markdown(f"# References\n\n{boilerplate}\n", boilerplate, cfg["heading_shift"]) == ""
    deep = track_references_markdown("##### Deep", "", cfg["heading_shift"])
    assert deep == "#" * MAX_HEADING_LEVEL + " Deep"


def test_references_config_points_at_the_references_file():
    cfg = load_config()
    assert (Path(cfg["_root"]) / cfg["references"]["file"]).exists()
