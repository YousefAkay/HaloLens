"""Tests for the privacy gate in scripts/make_submission.py. Owner: INT. Pure functions and a temp folder only."""

from __future__ import annotations

import importlib.util
import json

from leaselens.config import repo_root

_spec = importlib.util.spec_from_file_location("make_submission", repo_root() / "scripts" / "make_submission.py")
sub = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sub)


def test_clean_allowlisted_paths_pass():
    paths = ["src/leaselens/config.py", "data/public/sources.csv", "data/synthetic/lease_history.csv",
             "README.md", "outputs/public/aggregates_synthetic.json", "app/cache/qa_presets.json"]
    assert sub.path_violations(paths) == []


def test_each_forbidden_location_is_refused():
    for path in ["data/private/lease_history.csv", "outputs/private/aggregates.json", "models/champion.pkl",
                 ".venv/Lib/x.py", ".git/config", ".env", "scripts/.env", "outputs/submission/old.zip"]:
        assert sub.path_violations([path]), path


def test_csv_outside_public_and_synthetic_is_refused():
    assert sub.path_violations(["docs/notes.csv"])
    assert sub.path_violations(["data/other/table.csv"])


def test_sponsor_named_csv_is_allowed_only_in_synthetic():
    assert sub.path_violations(["data/public/lease_history.csv"])
    assert not sub.path_violations(["data/synthetic/lease_history.csv"])


def test_env_example_is_not_an_env_file():
    assert not sub.path_violations([".env.example"])


def test_collect_skips_caches_and_only_allowlisted_roots(tmp_path):
    for relative in ["src/a.py", "src/__pycache__/a.pyc", "tests/t.py", "README.md", "other/x.py", "data/private/z.csv",
                     "src/pkg.egg-info/PKG-INFO"]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    assert sub.collect(tmp_path) == ["README.md", "src/a.py", "tests/t.py"]


def test_preset_cache_must_be_marked_synthetic(tmp_path):
    cache = tmp_path / "app" / "cache" / "qa_presets.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"source": "synthetic aggregates", "answers": {}}), encoding="utf-8")
    assert sub.preset_cache_violation(tmp_path) is None
    cache.write_text(json.dumps({"source": "real aggregates", "answers": {}}), encoding="utf-8")
    assert sub.preset_cache_violation(tmp_path)


def _cell(*outputs, executed=1):
    return {"cell_type": "code", "source": ["x = 1"], "execution_count": executed, "outputs": list(outputs)}


def _html(*headers):
    return {"output_type": "display_data", "data": {"text/html": "<table><tr>" + "".join(
        f"<th>{header}</th>" for header in headers) + "</tr></table>"}}


def test_unit_identifier_header_is_flagged():
    problems, _ = sub.notebook_problems({"cells": [_cell(_html("hUnit", "rent"))]})
    assert any("column header" in problem for problem in problems)
    problems, _ = sub.notebook_problems({"cells": [_cell({"output_type": "execute_result",
                                                         "data": {"text/plain": "unit_code   rent\n0123  5"}})]})
    assert problems


def test_distinct_count_header_naming_hunit_is_not_a_leak():
    problems, _ = sub.notebook_problems({"cells": [_cell(_html("clé", "unités (hUnit)", "paires"))]})
    assert problems == []


def test_unexecuted_cell_and_error_output_block_the_build():
    problems, _ = sub.notebook_problems({"cells": [_cell(executed=None),
                                                  _cell({"output_type": "error", "ename": "E", "evalue": "x"})]})
    assert len(problems) == 2


def test_figures_are_counted():
    figure = {"output_type": "display_data", "data": {"image/png": "AAAA"}}
    assert sub.notebook_problems({"cells": [_cell(figure), _cell(figure)]})[1] == 2


def test_build_refuses_without_the_executed_notebook(tmp_path):
    assert sub.build(tmp_path) == sub.EXIT_REFUSED
    assert not (tmp_path / sub.ZIP_RELATIVE).exists()
