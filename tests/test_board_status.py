"""Tests for the done-matching rules in scripts/board_status.py. Owner: INT.

Pure functions, plus one test that runs git in a temporary repository (never the real history).
"""

from __future__ import annotations

import importlib.util
import subprocess

from leaselens.config import repo_root

_spec = importlib.util.spec_from_file_location("board_status", repo_root() / "scripts" / "board_status.py")
board_status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(board_status)

subject_lines = board_status.subject_lines
is_done = board_status.is_done
RECORD = board_status.RECORD_SEPARATOR


def test_id_in_commit_body_does_not_count():
    raw = f"[INT][I-05] Build notebook\n\nAlso touches I-13a and [INT][I-13a] in the body.{RECORD}"
    subjects = subject_lines(raw)
    assert subjects == ["[INT][I-05] Build notebook"]
    assert not is_done("I-13a", "INT", "", subjects)


def test_bracket_tag_matches_own_id_but_not_its_prefix_id():
    subjects = ["[INT][I-12a] Add number guard"]
    assert is_done("I-12a", "INT", "", subjects)
    assert not is_done("I-12", "INT", "", subjects)


def test_merge_subject_matches_own_id_only():
    subjects = ["Merge pull request #5 from YousefAkay/msr/M-02-pairs"]
    assert is_done("M-02", "MSR", "", subjects)
    assert not is_done("M-01", "MSR", "", subjects)
    assert not is_done("M-020", "MSR", "", subjects)


def test_int_tag_does_not_mark_msr_or_fct_tasks_done():
    subjects = ["[INT][I-13a] Section 01 in French"]
    assert is_done("I-13a", "INT", "", subjects)
    assert not is_done("I-13a", "MSR", "", subjects)
    assert not is_done("I-13a", "FCT", "", subjects)


def test_notes_starting_with_done_count():
    assert is_done("I-01", "INT", "done (merged in PR #2, int/I-01-scaffold)", [])
    assert is_done("I-01", "INT", "  Done in the earlier PR", [])
    assert not is_done("I-01", "INT", "not done yet", [])


def test_short_id_does_not_match_suffixed_task():
    subjects = ["[INT][I-01b] Autopilot", "Merge pull request #3 from YousefAkay/int/I-01b-autopilot"]
    assert not is_done("I-01", "INT", "", subjects)
    assert is_done("I-01b", "INT", "", subjects)


def test_subject_lines_takes_first_nonblank_line_of_each_commit():
    raw = f"\n[MSR][M-01] Pair tests\n\nbody line{RECORD}Merge pull request #5 from x/msr/M-01-pairs\n{RECORD}"
    assert subject_lines(raw) == ["[MSR][M-01] Pair tests", "Merge pull request #5 from x/msr/M-01-pairs"]


next_task = board_status.next_task


def _row(task_id: str, notes: str = "", workable: bool = True) -> dict:
    return {"id": task_id, "notes": notes, "workable": workable, "status": "todo",
            "continuous": False, "waiting_on": []}


def test_priority_row_beats_board_order():
    rows = [_row("I-05"), _row("I-06", notes="priority after M-04"), _row("I-07")]
    assert next_task(rows)[0]["id"] == "I-06"


def test_board_order_breaks_ties_between_priority_rows():
    rows = [_row("I-05", notes="priority"), _row("I-06", notes="Priority: soon")]
    assert next_task(rows)[0]["id"] == "I-05"


def test_priority_row_that_is_not_workable_is_ignored():
    rows = [_row("I-05"), _row("I-06", notes="priority", workable=False)]
    assert next_task(rows)[0]["id"] == "I-05"


def test_priority_must_start_the_notes():
    rows = [_row("I-05", notes="after M-04, not priority"), _row("I-06")]
    assert next_task(rows)[0]["id"] == "I-05"


def test_nothing_workable_returns_none():
    assert next_task([_row("I-05", workable=False)])[0] is None


def test_git_helper_reads_non_ascii_commit_messages(tmp_path, monkeypatch):
    """I-01f: a commit with non-ASCII characters (⚠️, é) must decode on any console code page, e.g. Windows cp1252."""
    message = "[INT][I-99] Warn about ⚠️ and é in a subject"
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false",
                    "commit", "-q", "--allow-empty", "-m", message], cwd=tmp_path, check=True)
    monkeypatch.setattr(board_status, "ROOT", tmp_path)
    raw = board_status.git("log", f"--format=%B{board_status.RECORD_SEPARATOR}")
    assert message in board_status.subject_lines(raw)
