"""Build the submission zip from an allowlist, behind a privacy gate. Owner: INT. Task I-15a.

Usage:
    python scripts/make_submission.py

Writes outputs/submission/HaloLens_submission.zip (gitignored). The zip holds the allowlisted repository files plus
the EXECUTED notebook from outputs/private/project_analysis.ipynb, placed at the zip root as project_analysis.ipynb.

Privacy gate (the build refuses, and writes nothing, when any rule trips):
- a path under data/private, outputs/private (other than the notebook), models/, .venv, .git or a .env file;
- a CSV outside data/public and data/synthetic; an portfolio_*.csv outside data/synthetic (the synthetic fixtures use the
  sponsor's file names, because the loader requires them);
- app/cache/qa_presets.json that is not marked as generated from synthetic aggregates;
- a notebook with an unexecuted code cell, an error output, or a unit identifier as a table column header in an output.
Headers are checked, not values: numeric unit IDs collide with ordinary counts, so a value match would be noise.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

from leaselens.config import repo_root

EXIT_OK = 0
EXIT_REFUSED = 1
ZIP_RELATIVE = Path("outputs") / "submission" / "HaloLens_submission.zip"
NOTEBOOK_SOURCE = Path("outputs") / "private" / "project_analysis.ipynb"
NOTEBOOK_NAME = "project_analysis.ipynb"
ALLOW_DIRECTORIES = ("src", "config", "scripts", "notebook/sections", "app", "tests", "data/public", "data/synthetic",
                     "docs", "outputs/public", ".streamlit")
ALLOW_FILES = ("README.md", "AGENTS.md", "requirements.txt", "pyproject.toml")
ALLOW_FILES = ("README.md", "AGENTS.md", "requirements.txt", "pyproject.toml", ".env.example")
SKIP_SUFFIXES = (".pyc", ".pyo")
SKIP_DIRECTORY_SUFFIX = ".egg-info"
FORBIDDEN_PARTS = {".venv", "venv", ".git", "models"}
FORBIDDEN_PREFIXES = ("data/private/", "outputs/private/", "outputs/submission/")
PRESET_CACHE = "app/cache/qa_presets.json"
PRESET_SOURCE_MARK = "synthetic"
UNIT_HEADERS = {"hunit", "unit_id", "unit_code", "sunitcode", "spropcode", "prop_code", "hproperty", "hbuilding",
                "ssite", "unit", "unité", "unite"}
TH_CELL = re.compile(r"<th[^>]*>(.*?)</th>", re.IGNORECASE | re.DOTALL)
TAG = re.compile(r"<[^>]+>")


def collect(root: Path) -> list[str]:
    """Posix paths (relative to the repository root) of every allowlisted file that exists."""
    found: list[str] = []
    for name in ALLOW_FILES:
        if (root / name).is_file():
            found.append(name)
    for directory in ALLOW_DIRECTORIES:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            relative = path.relative_to(root)
            parts = set(relative.parts)
            if (not path.is_file() or parts & SKIP_PARTS or path.suffix in SKIP_SUFFIXES
                    or any(part.endswith(SKIP_DIRECTORY_SUFFIX) for part in relative.parts)):
                continue
            found.append(relative.as_posix())
    return found


def path_violations(paths: list[str]) -> list[str]:
    """Reasons the path list may not be shipped. Empty when every path is allowed."""
    problems = []
    for path in paths:
        parts = set(Path(path).parts)
        name = Path(path).name
        if path.startswith(FORBIDDEN_PREFIXES) or parts & FORBIDDEN_PARTS:
            problems.append(f"forbidden location: {path}")
        elif name == ".env" or (name.startswith(".env") and name != ".env.example"):
            problems.append(f"environment file: {path}")
        elif path.endswith(".csv") and not path.startswith(("data/public/", "data/synthetic/")):
            problems.append(f"CSV outside data/public and data/synthetic: {path}")
        elif re.match(r"portfolio_.*\.csv$", name) and not path.startswith("data/synthetic/"):
            problems.append(f"sponsor-named CSV outside data/synthetic: {path}")
    return problems


def preset_cache_violation(root: Path) -> str | None:
    """The preset answers must have been generated from synthetic aggregates only."""
    path = root / PRESET_CACHE
    if not path.exists():
        return None
    try:
        source = str(json.loads(path.read_text(encoding="utf-8")).get("source", ""))
    except (OSError, ValueError):
        return f"{PRESET_CACHE} is not readable"
    return None if PRESET_SOURCE_MARK in source.lower() else f"{PRESET_CACHE} is not marked as synthetic"


def _output_text(output: dict, mime: str) -> str:
    value = output.get("data", {}).get(mime, "")
    return value if isinstance(value, str) else "".join(value)


def header_tokens(output: dict) -> set[str]:
    """Whole column headers (lower-cased) of the tables in one cell output: HTML <th> cells, or the cells of the first
    text line (split on runs of two spaces or more). A header such as "unités (hUnit)" is a distinct-count column, not an
    identifier column, so only a header that IS an identifier name matches."""
    headers: set[str] = set()
    for cell in TH_CELL.findall(_output_text(output, "text/html")):
        headers.add(" ".join(TAG.sub(" ", cell).split()).lower())
    lines = _output_text(output, "text/plain").splitlines()
    if lines:
        headers |= {cell.strip().lower() for cell in re.split(r"\s{2,}", lines[0]) if cell.strip()}
    return headers


def notebook_problems(notebook: dict) -> tuple[list[str], int]:
    """Gate failures for the executed notebook, and its embedded figure count."""
    problems: list[str] = []
    figures = 0
    unexecuted = errors = leaks = 0
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        if cell.get("execution_count") is None and "".join(cell.get("source", "")).strip():
            unexecuted += 1
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                errors += 1
            if "image/png" in output.get("data", {}):
                figures += 1
            if header_tokens(output) & UNIT_HEADERS:
                leaks += 1
    if unexecuted:
        problems.append(f"{unexecuted} unexecuted code cell(s)")
    if errors:
        problems.append(f"{errors} error output(s)")
    if leaks:
        problems.append(f"{leaks} output(s) with a unit-identifier column header")
    return problems, figures


def build(root: Path | None = None) -> int:
    root = root or repo_root()
    notebook_path = root / NOTEBOOK_SOURCE
    if not notebook_path.is_file():
        print(f"REFUSED: executed notebook not found at {NOTEBOOK_SOURCE.as_posix()}. Run build_notebook.py --real first.")
        return EXIT_REFUSED
    paths = collect(root)
    problems = path_violations(paths)
    cache_problem = preset_cache_violation(root)
    if cache_problem:
        problems.append(cache_problem)
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    notebook_issues, figures = notebook_problems(notebook)
    problems.extend(notebook_issues)
    if problems:
        print(f"REFUSED: {len(problems)} privacy-gate problem(s); nothing written.")
        for problem in problems:
            print(f"  - {problem}")
        return EXIT_REFUSED

    target = root / ZIP_RELATIVE
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(root / path, path)
        archive.write(notebook_path, NOTEBOOK_NAME)

    with zipfile.ZipFile(target) as archive:  # the gate runs again on what was actually written
        written = [name for name in archive.namelist() if name != NOTEBOOK_NAME]
    final_problems = path_violations(written)
    if final_problems:
        target.unlink()
        print("REFUSED after writing; zip deleted: " + "; ".join(final_problems))
        return EXIT_REFUSED

    with zipfile.ZipFile(target) as archive:
        entries = archive.namelist()
    top_level = sorted({entry.split("/")[0] for entry in entries})
    print(f"Wrote {ZIP_RELATIVE.as_posix()}")
    print(f"Files: {len(entries)} · size: {target.stat().st_size / 1024:.0f} KiB · figures in notebook: {figures}")
    print("Top-level entries: " + ", ".join(top_level))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(build())
