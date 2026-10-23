"""Assemble notebook/sections/*.py (jupytext percent) into one notebook and execute it on a clean kernel.

Owner: INT. Task I-05.

Usage (run from anywhere; paths resolve from the repository root):
    python scripts/build_notebook.py               # data mode from config/core.yaml (real by default)
    python scripts/build_notebook.py --synthetic   # committed fixtures in data/synthetic
    python scripts/build_notebook.py --real        # CRM data in data/private; output goes to outputs/private
    python scripts/build_notebook.py --no-execute  # assemble only, do not run the cells

The build fails (exit code 1) on the first cell that raises. Real-mode output is gitignored because an
executed notebook contains CRM aggregates.
"""

from __future__ import annotations

import argparse
import copy
import os
import sys
from pathlib import Path

import jupytext
import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

from halolens.config import MODE_ENV_VAR, load_config, output_dir, repo_root

SECTIONS_DIR = "notebook/sections"


def section_files(sections_dir: Path) -> list[Path]:
    """Section files in filename order. The numeric prefix (00_ … 12_, with 11a before 11b) sets the order."""
    return sorted(sections_dir.glob("*.py"))


def assemble(sections_dir: Path, kernel_name: str) -> nbformat.NotebookNode:
    """Concatenate the cells of every section file into one notebook, without running it."""
    cells = []
    for path in section_files(sections_dir):
        cells.extend(jupytext.read(path).cells)
    notebook = nbformat.v4.new_notebook(cells=cells)
    notebook.metadata["kernelspec"] = {"name": kernel_name, "display_name": "Python 3", "language": "python"}
    return notebook


def execute(notebook: nbformat.NotebookNode, kernel_name: str, timeout: int) -> nbformat.NotebookNode:
    """Run every cell in a freshly started kernel from the repository root. Raises CellExecutionError on failure."""
    client = NotebookClient(
        notebook,
        kernel_name=kernel_name,
        timeout=timeout,
        resources={"metadata": {"path": str(repo_root())}},
    )
    return client.execute()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Halo Lens analysis notebook.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--synthetic", action="store_true", help="run on the committed synthetic fixtures")
    mode.add_argument("--real", action="store_true", help="run on the CRM data in data/private")
    parser.add_argument("--no-execute", action="store_true", help="assemble the notebook without running it")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    requested = "real" if args.real else "synthetic" if args.synthetic else None
    cfg = load_config(mode=requested)
    mode = cfg["data"]["mode"]
    build = cfg["build"]

    # The notebook's first cell calls load_config(), which reads this variable, so both use the same mode.
    os.environ[MODE_ENV_VAR] = mode

    notebook = assemble(repo_root() / SECTIONS_DIR, build["kernel_name"])
    out_dir = output_dir(cfg) if mode == "real" else repo_root()
    out_path = out_dir / build["notebook_file"]

    if not args.no_execute:
        try:
            notebook = execute(notebook, build["kernel_name"], build["cell_timeout_seconds"])
        except CellExecutionError as error:
            print(f"BUILD FAILED in mode={mode}: a notebook cell raised an error.", file=sys.stderr)
            print(str(error), file=sys.stderr)
            return 1

    nbformat.write(notebook, out_path)
    print(f"Wrote {out_path.relative_to(repo_root())} ({len(notebook.cells)} cells, mode={mode}, "
          f"executed={not args.no_execute})")
    if mode == "real":
        # The jury runs the notebook on their own copy of the CRM files: ship the source with outputs cleared,
        # so no CRM aggregate is written next to the code. The executed copy stays in the gitignored outputs/private.
        jury_copy = copy.deepcopy(notebook)
        for cell in jury_copy.cells:
            if cell.cell_type == "code":
                cell.outputs = []
                cell.execution_count = None
        jury_path = repo_root() / build["notebook_file"]
        nbformat.write(jury_copy, jury_path)
        print(f"Wrote {jury_path.relative_to(repo_root())} (source only, outputs cleared, for the jury)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
