"""Export the aggregates JSON from the pipeline. Owner: INT. Task I-09.

Usage:
    python scripts/export_aggregates.py --synthetic   # committed fixtures -> outputs/public/aggregates_synthetic.json
    python scripts/export_aggregates.py --real        # your CSVs in data/private -> outputs/private/aggregates.json

--real writes a gitignored file that holds CRM-derived aggregates; never commit it. Its console output is limited to
the headline, the model, the number of backtest rows and the coverage counts.
Seeds come from config/core.yaml (random_seed); the pipeline itself is deterministic.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from leaselens.config import data_dir, load_config, output_dir, repo_root, source_files
from leaselens.export.aggregates import build_aggregates, export
from leaselens.io import canonicalize, load_raw
from leaselens.market.registry import load_external

EXIT_OK = 0


def pct(value) -> str:
    return "n/a" if value is None else f"{value:.1f} %"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export aggregates (counts and percentages only).")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--synthetic", action="store_true", help="committed synthetic fixtures")
    mode.add_argument("--real", action="store_true", help="your CSVs in data/private")
    args = parser.parse_args(argv)

    cfg = load_config(mode="real" if args.real else "synthetic")
    np.random.seed(cfg["random_seed"])
    tables = canonicalize(load_raw(data_dir(cfg), source_files=source_files(cfg)))
    external = load_external(repo_root() / cfg["data"]["public_dir"] / cfg["external"]["sources_file"])
    document = build_aggregates(tables, external, cfg)

    if args.real:
        path = output_dir(cfg) / cfg["outputs"]["aggregates_file"]
    else:
        path = repo_root() / cfg["outputs"]["public_dir"] / cfg["outputs"]["aggregates_synthetic_file"]
    export(document, path)

    headline, coverage = document["headline"], document["coverage"]
    print(f"Wrote {path.relative_to(repo_root()).as_posix()} (mode={cfg['data']['mode']})")
    print(f"Headline net {pct(headline['net_pct'])} · contractual {pct(headline['contract_pct'])} · "
          f"model {headline['model'] or 'n/a'}")
    print(f"Backtest rows: {len(document['backtest'])}")
    print("Coverage: " + " · ".join(f"{name} {value}" for name, value in coverage.items()))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
