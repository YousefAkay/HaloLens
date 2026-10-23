"""The Markdown of the reader-facing sections names no task, rule document or track.

Sections 00, 01, 02, 11a and 12 are the ones a reader meets first. Their Markdown must not carry task IDs,
references to AGENTS.md sections, or a track tag such as (INT).
"""

from __future__ import annotations

import re

import jupytext
import pytest

from halolens.config import repo_root

SECTIONS = ["00_executive", "01_definition", "02_data_dictionary_qa", "11a_uncertainty", "12_references"]
TASK_ID = re.compile(r"\b[IMF]-\d{2}[a-z]?\b")
AGENTS_SECTION = re.compile(r"AGENTS\.md §")
TRACK_TAG = re.compile(r"\((INT|MSR|FCT)\)")


def _markdown_lines(name: str) -> list[str]:
    path = repo_root() / "notebook" / "sections" / f"{name}.py"
    cells = jupytext.read(path).cells
    return [line for cell in cells if cell.cell_type == "markdown" for line in cell.source.splitlines()]


@pytest.mark.parametrize("name", SECTIONS)
def test_markdown_has_no_task_ids(name):
    assert [line for line in _markdown_lines(name) if TASK_ID.search(line)] == []


@pytest.mark.parametrize("name", SECTIONS)
def test_markdown_does_not_cite_agents_sections(name):
    assert [line for line in _markdown_lines(name) if AGENTS_SECTION.search(line)] == []


@pytest.mark.parametrize("name", SECTIONS)
def test_markdown_has_no_standalone_track_tag(name):
    lines = _markdown_lines(name)
    assert [line for line in lines if TRACK_TAG.search(line)] == []


def test_the_patterns_catch_what_they_should_and_spare_the_rest():
    assert (
        TASK_ID.search("tâche I" + "-13") and TASK_ID.search("(M" + "-03b)") and TASK_ID.search("F" + "-05"))
    assert not TASK_ID.search("section 10") and not TASK_ID.search("la hausse de -12 points")
    assert AGENTS_SECTION.search("(AGENTS.md §9.1)") and not AGENTS_SECTION.search("AGENTS.md")
    assert TRACK_TAG.search("Références (INT)") and not TRACK_TAG.search("INT et MSR")
