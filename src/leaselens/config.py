"""Configuration loading. Owner: INT.

Merges config/core.yaml, config/measure.yaml and config/forecast.yaml into one dict.
Each top-level key must live in exactly one file; duplicates raise an error.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import yaml

CONFIG_FILES = ("core.yaml", "measure.yaml", "forecast.yaml")
MODE_ENV_VAR = "LEASELENS_DATA_MODE"  # set by scripts/build_notebook.py so the notebook runs in the same mode


def repo_root() -> Path:
    """Repository root (the folder containing config/)."""
    return Path(__file__).resolve().parents[2]


def load_config(root: Path | None = None, mode: str | None = None) -> dict:
    """Load and merge the three YAML files.

    `mode` overrides data.mode ("synthetic" or "real"). When it is None, the MODE_ENV_VAR environment
    variable is used if set; otherwise the value in core.yaml stands.
    """
    root = Path(root) if root else repo_root()
    mode = mode or os.environ.get(MODE_ENV_VAR) or None
    merged: dict = {}
    for name in CONFIG_FILES:
        with open(root / "config" / name, encoding="utf-8") as handle:
            part = yaml.safe_load(handle) or {}
        duplicates = set(part) & set(merged)
        if duplicates:
            raise ValueError(f"Config keys defined in more than one file: {sorted(duplicates)} ({name})")
        merged.update(part)
    if mode is not None:
        if mode not in ("synthetic", "real"):
            raise ValueError("mode must be 'synthetic' or 'real'")
        merged["data"]["mode"] = mode
    merged["_root"] = str(root)
    return merged


def data_dir(cfg: dict) -> Path:
    """Folder holding the four source CSVs + manifest for the configured mode."""
    key = "private_dir" if cfg["data"]["mode"] == "real" else "synthetic_dir"
    return Path(cfg["_root"]) / cfg["data"][key]


def output_dir(cfg: dict) -> Path:
    """Where derived artifacts go: private for real data, public for synthetic."""
    key = "private_dir" if cfg["data"]["mode"] == "real" else "public_dir"
    path = Path(cfg["_root"]) / cfg["outputs"][key]
    path.mkdir(parents=True, exist_ok=True)
    return path


def cutoff_for(year: int, cfg: dict) -> pd.Timestamp:
    """Forecast cutoff for target `year`: December 31 of year − 1 (configurable month-day)."""
    return pd.Timestamp(f"{year - 1}-{cfg['forecast_years']['cutoff_month_day']}")
