"""Fails if anything confidential is tracked by git."""

import subprocess
from pathlib import Path

import pytest

from halolens.config import repo_root
from halolens.contracts import SOURCE_FILES

ALLOWED_CSV_PREFIXES = ("data/public/", "data/synthetic/")
FORBIDDEN_PREFIXES = ("data/private/", "outputs/private/", "models/")


def _tracked_files() -> list[str]:
    try:
        output = subprocess.run(["git", "ls-files"], cwd=repo_root(), capture_output=True, encoding="utf-8",
                                errors="replace", check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return output.stdout.splitlines()


def test_no_private_paths_tracked():
    tracked = _tracked_files()
    assert not [path for path in tracked if path.startswith(FORBIDDEN_PREFIXES)]


def test_csv_only_in_allowed_folders():
    tracked = _tracked_files()
    assert not [p for p in tracked if p.endswith(".csv") and not p.startswith(ALLOWED_CSV_PREFIXES)]


def test_crm_file_names_only_as_synthetic():
    tracked = _tracked_files()
    crm_names = set(SOURCE_FILES.values())
    offenders = [p for p in tracked if Path(p).name in crm_names and not p.startswith("data/synthetic/")]
    assert not offenders


def test_no_env_file_tracked():
    assert ".env" not in [Path(p).name for p in _tracked_files()]
