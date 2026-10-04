"""External observation registry with release-date filtering.

Owner: MSR. Implements `load_external` and `as_of` (AGENTS.md Section 7.3) plus `validate_external`.

`data/public/sources.csv` holds human-verified public observations (contracts.EXTERNAL_COLUMNS). Every row
carries the date the value became public (`release_date`); `as_of` is the only gate analysis code uses to
keep forecasts free of information published after a cutoff.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from leaselens.contracts import EXTERNAL_COLUMNS

DATE_COLUMNS = ["ref_period_start", "ref_period_end", "release_date", "accessed_date"]
TEXT_COLUMNS = [column for column in EXTERNAL_COLUMNS if column not in DATE_COLUMNS + ["value"]]
OBSERVATION_KEY = ["series_id", "geography", "metric", "ref_period_start", "ref_period_end", "release_date"]


def load_external(path) -> pd.DataFrame:
    """Read data/public/sources.csv into contracts.EXTERNAL_COLUMNS with parsed dates.

    Input: path to a CSV in the EXTERNAL schema. Output: DataFrame with exactly EXTERNAL_COLUMNS in contract
    order; date columns as datetime64, `value` as float, text columns as str ("" when blank).
    Raises ValueError when a contract column is missing, a date or value does not parse, or a row has no
    `release_date` (an observation without a release date cannot be placed in time, so it is unusable).
    """
    return parse_external(pd.read_csv(Path(path), dtype=str, keep_default_na=False))


def parse_external(raw: pd.DataFrame) -> pd.DataFrame:
    """Type an all-string EXTERNAL table (as read from CSV); same rules and errors as `load_external`."""
    missing = [column for column in EXTERNAL_COLUMNS if column not in raw.columns]
    if missing:
        raise ValueError(f"External sources file is missing contract columns: {missing}")

    external = raw[EXTERNAL_COLUMNS].copy()
    for column in TEXT_COLUMNS:
        external[column] = external[column].str.strip()
    for column in DATE_COLUMNS:
        external[column] = pd.to_datetime(external[column].str.strip().replace("", None), errors="raise")
    external["value"] = pd.to_numeric(external["value"].str.strip(), errors="raise").astype(float)

    if external["release_date"].isna().any():
        raise ValueError(f"{int(external['release_date'].isna().sum())} external rows have no release_date")
    return external


def as_of(external: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Keep only observations whose release_date is on or before cutoff.

    The cutoff day is inclusive. A row whose reference period ends before the cutoff but which was released
    after it is dropped: what matters is when the number was public, not what period it describes.
    Returns a new DataFrame; the input is not modified.
    """
    cutoff = pd.Timestamp(cutoff)
    return external.loc[external["release_date"] <= cutoff].copy()


def validate_external(external: pd.DataFrame, cfg: dict) -> list[str]:
    """Return a list of problems in a loaded EXTERNAL table (empty list = valid).

    Checks: `metric` and `extracted_by` use the values allowed in `cfg["external"]`; every row is verified
    (`verified_by` non-empty) and has a `url`; reference periods are ordered; nothing is released before its
    reference period starts, except metrics listed in `cfg["external"]["announced_ahead_metrics"]` (rules
    published before the year they apply to); no duplicate observation key.
    """
    settings = cfg["external"]
    announced_ahead = external["metric"].isin(settings.get("announced_ahead_metrics", []))
    problems = []
    unknown_metrics = sorted(set(external["metric"]) - set(settings["metrics"]))
    if unknown_metrics:
        problems.append(f"unknown metric values: {unknown_metrics}")
    unknown_provenance = sorted(set(external["extracted_by"]) - set(settings["extracted_by_values"]))
    if unknown_provenance:
        problems.append(f"unknown extracted_by values: {unknown_provenance}")
    checks = {
        "rows without verified_by": external["verified_by"] == "",
        "rows without url": external["url"] == "",
        "rows with ref_period_end before ref_period_start": external["ref_period_end"] < external["ref_period_start"],
        "rows released before their reference period starts": (
            (external["release_date"] < external["ref_period_start"]) & ~announced_ahead),
        "duplicate observations": external.duplicated(OBSERVATION_KEY, keep=False),
    }
    for label, failed in checks.items():
        if failed.any():
            problems.append(f"{int(failed.sum())} {label}")
    return problems
