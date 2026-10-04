"""Tests for the pure helpers in scripts/preflight.py. Owner: INT.

Only the decision logic is tested here. The git, pip and data checks run for real when preflight runs.
"""

from __future__ import annotations

import importlib.util

from leaselens.config import repo_root

_spec = importlib.util.spec_from_file_location("preflight", repo_root() / "scripts" / "preflight.py")
preflight = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(preflight)


def test_valid_track_accepts_only_the_three_codes():
    assert preflight.valid_track("INT\n")
    assert preflight.valid_track("MSR")
    assert not preflight.valid_track("int")
    assert not preflight.valid_track("INT MSR")
    assert not preflight.valid_track("")


def test_missing_sources_lists_every_absent_required_file():
    present = {"lease_history.csv", "manifest.json"}
    missing = preflight.missing_sources(present)
    assert "lease_history.csv" not in missing
    assert "manifest.json" not in missing
    assert len(missing) == len(preflight.required_data_files()) - 2


def test_complete_folder_has_nothing_missing():
    assert preflight.missing_sources(set(preflight.required_data_files())) == []


def test_env_file_outside_root_is_misplaced():
    paths = [".env", "data/.env", "sub/dir/.env", "notes.env"]
    assert preflight.misplaced_env_files(paths) == ["data/.env", "sub/dir/.env"]


def test_env_at_root_is_not_misplaced():
    assert preflight.misplaced_env_files([".env"]) == []


def test_requirements_change_detected_from_changed_files():
    assert preflight.requirements_changed("abc123", ["requirements.txt", "docs/x.md"])
    assert not preflight.requirements_changed("abc123", ["docs/x.md"])


def test_missing_install_record_always_counts_as_changed():
    assert preflight.requirements_changed(None, [])


def test_clean_tree_on_dev_needs_no_action():
    assert preflight.worktree_action("", "dev") == "ok"


def test_clean_tree_on_a_branch_switches_to_dev():
    assert preflight.worktree_action("", "int/I-01d-next-preflight") == "switch"


def test_detached_head_counts_as_not_on_dev():
    assert preflight.worktree_action("", "") == "switch"


def test_modified_file_stops_even_on_a_branch():
    assert preflight.worktree_action(" M AGENTS.md\n", "int/I-01d-next-preflight") == "dirty"


def test_untracked_file_counts_as_uncommitted():
    assert preflight.worktree_action("?? scratch.txt\n", "dev") == "dirty"
