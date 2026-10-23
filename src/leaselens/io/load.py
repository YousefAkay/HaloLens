"""Typed loading of the source CSVs with SHA-256 verification. Owner: INT.

This is the only module that reads source files. Source files are never modified.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from leaselens.contracts import SOURCE_FILES, SOURCE_ID_COLUMNS

HASH_CHUNK_BYTES = 1 << 20  # read files 1 MiB at a time when hashing


def file_sha256(path: Path) -> str:
    """SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(data_dir: Path, manifest_name: str = "manifest.json",
                    source_files: dict[str, str] | None = None) -> dict[str, bool]:
    """Compare each source CSV's hash with the manifest. Raises if any differs or is missing."""
    with open(Path(data_dir) / manifest_name, encoding="utf-8") as handle:
        manifest = json.load(handle)
    expected = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    results = {}
    for file_name in (source_files or SOURCE_FILES).values():
        if file_name not in expected:
            raise ValueError(f"{file_name} is not listed in {manifest_name}")
        actual = file_sha256(Path(data_dir) / file_name)
        results[file_name] = actual == expected[file_name]
    mismatched = [name for name, ok in results.items() if not ok]
    if mismatched:
        raise ValueError(f"Source files differ from the manifest (modified or wrong files): {mismatched}")
    return results


def load_raw(data_dir, verify: bool = True, manifest_name: str = "manifest.json",
             source_files: dict[str, str] | None = None) -> dict[str, pd.DataFrame]:
    """Read the four source tables with identifier columns as strings.

    Returns {"listings", "leases", "concessions", "asking"} with original column names.
    Dates are NOT parsed here; io.dictionary.canonicalize parses them once.
    `source_files` maps logical names to file names (default `contracts.SOURCE_FILES`; see `config.source_files`).
    """
    source_files = source_files or SOURCE_FILES
    data_dir = Path(data_dir)
    if verify:
        verify_manifest(data_dir, manifest_name, source_files)
    id_types = {column: str for column in SOURCE_ID_COLUMNS}
    return {
        logical: pd.read_csv(data_dir / file_name, dtype=id_types)
        for logical, file_name in source_files.items()
    }
