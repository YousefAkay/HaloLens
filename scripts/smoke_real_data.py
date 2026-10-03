"""Integration #1 smoke run: loaders, consecutive-lease pairs and the point-in-time snapshot. Owner: INT. Task I-07.

Usage:
    python scripts/smoke_real_data.py              # data mode from config/core.yaml (synthetic by default)
    python scripts/smoke_real_data.py --synthetic  # committed fixtures in data/synthetic
    python scripts/smoke_real_data.py --real       # sponsor CSVs in data/private (AGENTS.md §3.1)

Prints row counts, exclusion counts and snapshot counts only. It never prints rows, unit codes or hUnit values.
External observations are an empty table until the MSR registry loader (M-03) lands.
Exit code 0 when the run completes; EXIT_MISSING_DATA when real mode has no data folder.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

import pandas as pd

from leaselens.config import cutoff_for, data_dir, load_config, repo_root
from leaselens.contracts import EXTERNAL_COLUMNS
from leaselens.forecast.asof import make_snapshot
from leaselens.io import canonicalize, load_raw
from leaselens.measure.pairs import REASON_SEPARATOR, build_pairs

EXIT_OK = 0
EXIT_MISSING_DATA = 2


def empty_external() -> pd.DataFrame:
    """External observations with the contract columns and no rows (registry loader pending, M-03)."""
    frame = pd.DataFrame(columns=EXTERNAL_COLUMNS)
    frame["release_date"] = pd.to_datetime(frame["release_date"])
    return frame


def exclusion_counts(pairs: pd.DataFrame) -> Counter:
    """Number of excluded pairs per reason. A pair with several reasons counts once for each."""
    reasons: Counter = Counter()
    for text in pairs.loc[~pairs["eligible"], "exclusion_reason"]:
        reasons.update(text.split(REASON_SEPARATOR))
    return reasons


def report(title: str, rows: dict) -> None:
    print(title)
    for label, value in rows.items():
        print(f"  {label:<40} {value}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Counts-only integration smoke run.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--synthetic", action="store_true", help="run on the committed synthetic fixtures")
    mode.add_argument("--real", action="store_true", help="run on the sponsor CSVs in data/private")
    args = parser.parse_args(argv)

    cfg = load_config(mode="real" if args.real else "synthetic" if args.synthetic else None)
    folder = data_dir(cfg)
    if cfg["data"]["mode"] == "real" and not folder.exists():
        print(f"{folder.relative_to(repo_root()).as_posix()}/ not found. Place the four sponsor CSVs and manifest.json there "
              f"(AGENTS.md §3.1), then rerun with --real.", file=sys.stderr)
        return EXIT_MISSING_DATA

    raw = load_raw(folder)
    tables = canonicalize(raw)
    pairs = build_pairs(tables.leases, cfg)
    cutoff = cutoff_for(cfg["forecast_years"]["target_year"], cfg)
    snapshot = make_snapshot(tables, empty_external(), cutoff)
    snapshot_pairs = build_pairs(snapshot.leases, cfg)

    report(f"Mode: {cfg['data']['mode']}", {})
    report("Loaded tables (rows)", {
        "leases": len(tables.leases),
        "concessions": len(tables.concessions),
        "asking": len(tables.asking),
        "listings (units)": len(tables.units) if tables.units is not None else 0,
        "units (distinct unit key)": tables.leases[cfg["pairs"]["unit_key"]].drop_duplicates().shape[0],
    })
    report("Pairs, full history", {
        "consecutive pairs": len(pairs),
        "eligible": int(pairs["eligible"].sum()),
        **{f"excluded: {reason}": count for reason, count in sorted(exclusion_counts(pairs).items())},
    })
    report(f"Snapshot at cutoff {cutoff.date().isoformat()}", {
        "leases kept": len(snapshot.leases),
        "concessions kept": len(snapshot.concessions),
        "asking kept": len(snapshot.asking),
        "listings kept (None = not knowable)": 0 if snapshot.units is None else len(snapshot.units),
        "external observations kept": len(snapshot.external),
        "pairs from snapshot leases": len(snapshot_pairs),
        "eligible pairs from snapshot leases": int(snapshot_pairs["eligible"].sum()),
    })
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
