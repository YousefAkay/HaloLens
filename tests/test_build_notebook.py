"""Tests for scripts/build_notebook.py and the MODE_ENV_VAR override. Owner: INT.

Runs on the repository's section files and the synthetic configuration. The failure test uses a temporary
section folder, so no real or committed notebook is touched.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import jupytext
import pytest
from nbclient.exceptions import CellExecutionError

from halolens.config import MODE_ENV_VAR, load_config, repo_root

SECTIONS = repo_root() / "notebook" / "sections"


def _load_build_module():
    spec = importlib.util.spec_from_file_location("build_notebook", repo_root() / "scripts" / "build_notebook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = _load_build_module()


def test_section_order_follows_numeric_prefix():
    names = [path.name for path in build.section_files(SECTIONS)]
    assert names[0] == "00_executive.py"
    assert names[-1] == "12_references.py"
    assert names.index("11a_uncertainty.py") < names.index("11b_scenarios.py")
    assert names.index("10_forecast_2026.py") < names.index("11a_uncertainty.py")


def test_every_section_starts_with_markdown():
    for path in build.section_files(SECTIONS):
        first_cell = jupytext.read(path).cells[0]
        assert first_cell.cell_type == "markdown", path.name


def test_assemble_concatenates_all_sections():
    notebook = build.assemble(SECTIONS, kernel_name="python3")
    expected = sum(len(jupytext.read(path).cells) for path in build.section_files(SECTIONS))
    assert len(notebook.cells) == expected
    assert notebook.metadata["kernelspec"]["name"] == "python3"


def test_mode_env_var_overrides_core_yaml(monkeypatch):
    monkeypatch.setenv(MODE_ENV_VAR, "real")
    assert load_config()["data"]["mode"] == "real"
    monkeypatch.delenv(MODE_ENV_VAR)
    assert load_config()["data"]["mode"] == load_config(mode=None)["data"]["mode"]


def test_explicit_mode_beats_env_var(monkeypatch):
    monkeypatch.setenv(MODE_ENV_VAR, "real")
    assert load_config(mode="synthetic")["data"]["mode"] == "synthetic"


def test_execute_raises_on_failing_cell(tmp_path: Path):
    (tmp_path / "00_broken.py").write_text(
        "# %% [markdown]\n# ## Broken\n\n# %%\nraise RuntimeError('boom')\n",
        encoding="utf-8",
    )
    notebook = build.assemble(tmp_path, kernel_name="python3")
    cfg = load_config(mode="synthetic")
    with pytest.raises(CellExecutionError, match="boom"):
        build.execute(notebook, "python3", cfg["build"]["cell_timeout_seconds"])
