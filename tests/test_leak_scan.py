"""Tests for scripts/leak_scan.py on a temporary git repo with fake terms only."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("leak_scan", ROOT / "scripts" / "leak_scan.py")
leak_scan = importlib.util.module_from_spec(SPEC)
sys.modules["leak_scan"] = leak_scan
SPEC.loader.exec_module(leak_scan)

FAKE_TERM = "Zorblax Industries"
FAKE_COLUMN = "fakeColumnQ"
FAKE_COUNT = "7,777"
FAKE_EMAIL = "zed.quux@example.invalid"

DENYLIST = f"""
excluded_paths: ["skipme/**"]
special_checks:
  any_email: {{enabled: true, allowed_emails: ['tester@example.invalid']}}
  coauthored_trailer: {{enabled: true}}
  claude_author: {{enabled: true}}
  generated_with: {{enabled: true}}
rules:
  - name: fake_names
    type: literal
    patterns: ["{FAKE_TERM}"]
  - name: fake_schema
    type: literal
    patterns: ["{FAKE_COLUMN}"]
    allowed_paths: ["src/*"]
  - name: fake_counts
    type: regex
    patterns: ['(?<!\\w)7[ ,.]?777(?!\\w)']
"""


def run(repo: Path, *args: str, env_user: tuple[str, str] = ("Tester", "tester@example.invalid")) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(repo),
            "GIT_AUTHOR_NAME": env_user[0],
            "GIT_AUTHOR_EMAIL": env_user[1],
            "GIT_COMMITTER_NAME": env_user[0],
            "GIT_COMMITTER_EMAIL": env_user[1],
        },
    )


def commit(repo: Path, files: dict[str, str | None], message: str, user: tuple[str, str] = ("Tester", "tester@example.invalid")) -> None:
    for rel, content in files.items():
        target = repo / rel
        if content is None:
            target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    run(repo, "add", "-A", env_user=user)
    run(repo, "commit", "-q", "-m", message, env_user=user)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    run(r, "init", "-q", "-b", "main")
    (r / ".gitignore").write_text("config/\noutputs/\n", encoding="utf-8")  # keep the denylist files untracked
    (r / "config").mkdir()
    shutil.copyfile(ROOT / "config" / "leak_denylist.example.yaml", r / "config" / "leak_denylist.example.yaml")
    deny = r / "outputs" / "private" / "leak_denylist.yaml"
    deny.parent.mkdir(parents=True)
    deny.write_text(DENYLIST, encoding="utf-8")
    commit(r, {"README.txt": "clean file\n"}, "initial commit")
    return r


def scan(repo: Path, *args: str, capsys) -> tuple[int, str]:
    code = leak_scan.main(["--repo", str(repo), *args])
    return code, capsys.readouterr().out


def test_clean_repo_exits_zero(repo, capsys):
    code, out = scan(repo, capsys=capsys)
    assert code == 0
    assert "RESULT: clean" in out


def test_tree_hit_is_reported_by_path_and_exit_1(repo, capsys):
    commit(repo, {"docs_a/notes.txt": f"about {FAKE_TERM.lower()} here\n"}, "add notes")
    code, out = scan(repo, "--tree-only", capsys=capsys)
    assert code == 1
    assert "[fake_names]" in out
    assert "docs_a/notes.txt" in out


def test_regex_rule_matches_variants(repo, capsys):
    commit(repo, {"a.txt": f"count {FAKE_COUNT} units\n", "b.txt": "id 17777 is not a hit\n"}, "counts")
    code, out = scan(repo, "--tree-only", capsys=capsys)
    assert code == 1
    assert "a.txt" in out and "b.txt" not in out


def test_allowed_paths_tolerate_hits(repo, capsys):
    commit(repo, {"src/io.py": f"col = '{FAKE_COLUMN}'\n"}, "schema in allowed path")
    code, _ = scan(repo, "--tree-only", capsys=capsys)
    assert code == 0
    commit(repo, {"app/ui.py": f"col = '{FAKE_COLUMN}'\n"}, "schema in other path")
    code, out = scan(repo, "--tree-only", capsys=capsys)
    assert code == 1 and "app/ui.py" in out and "src/io.py" not in out


def test_excluded_paths_skipped_in_tree(repo, capsys):
    commit(repo, {"skipme/x.txt": f"{FAKE_TERM}\n"}, "excluded file")
    code, _ = scan(repo, "--tree-only", capsys=capsys)
    assert code == 0


def test_history_finds_removed_content(repo, capsys):
    commit(repo, {"leaky.txt": f"{FAKE_TERM}\n"}, "add leak")
    commit(repo, {"leaky.txt": None}, "remove leak")
    code, out = scan(repo, "--tree-only", capsys=capsys)
    assert code == 0
    code, out = scan(repo, capsys=capsys)
    assert code == 1
    assert "== git history" in out and "leaky.txt" in out
    short = run(repo, "log", "--all", "--format=%h", "-n", "2").stdout.split()
    assert any(h in out for h in short)


def test_history_scans_commit_messages_and_trailers(repo, capsys):
    commit(repo, {"b.txt": "ok\n"}, f"mention {FAKE_TERM}\n\nCo-Authored-By: Someone <x@example.invalid>")
    code, out = scan(repo, capsys=capsys)
    assert code == 1
    for rule in ("fake_names", "coauthored_trailer", "any_email"):
        assert f"[{rule}]" in out
    assert "<commit-message>" in out


def test_claude_author_and_generated_with(repo, capsys):
    commit(repo, {"c.txt": "ok\n"}, "Generated with a tool", user=("Claude Helper", "h@example.invalid"))
    code, out = scan(repo, capsys=capsys)
    assert code == 1
    assert "[claude_author]" in out and "[generated_with]" in out


def test_email_in_tree_and_allowed_email(repo, capsys):
    commit(repo, {"mail.txt": f"contact {FAKE_EMAIL}\n"}, "add email")
    code, out = scan(repo, "--tree-only", capsys=capsys)
    assert code == 1 and "[any_email]" in out
    deny = repo / "outputs" / "private" / "leak_denylist.yaml"
    deny.write_text(DENYLIST.replace("allowed_emails: ['tester@example.invalid']", f"allowed_emails: ['tester@example.invalid', '{FAKE_EMAIL}']"), encoding="utf-8")
    code, out = scan(repo, "--tree-only", capsys=capsys)
    assert code == 0


def test_output_never_contains_matched_text(repo, capsys):
    commit(
        repo,
        {"p.txt": f"{FAKE_TERM} {FAKE_COUNT} {FAKE_COLUMN} {FAKE_EMAIL}\n"},
        f"msg with {FAKE_TERM} and {FAKE_EMAIL}",
    )
    code, out = scan(repo, capsys=capsys)
    assert code == 1
    for secret in (FAKE_TERM, FAKE_TERM.lower(), FAKE_COUNT, FAKE_COLUMN, FAKE_EMAIL):
        assert secret not in out
    code, out = scan(repo, "--baseline", capsys=capsys)
    baseline = (repo / "outputs" / "private" / "leak_baseline.json").read_text(encoding="utf-8")
    for secret in (FAKE_TERM, FAKE_COUNT, FAKE_COLUMN, FAKE_EMAIL):
        assert secret not in baseline and secret not in out


def test_baseline_writes_counts_and_exits_zero(repo, capsys):
    commit(repo, {"q.txt": f"{FAKE_TERM}\n"}, "leak")
    code, _ = scan(repo, "--baseline", capsys=capsys)
    assert code == 0
    data = json.loads((repo / "outputs" / "private" / "leak_baseline.json").read_text(encoding="utf-8"))
    assert data["tree"]["fake_names"]["hit_lines"] == 1
    assert data["history"]["fake_names"]["hit_lines"] >= 1


def test_missing_denylist_is_created_from_example(tmp_path, capsys):
    r = tmp_path / "fresh"
    r.mkdir()
    run(r, "init", "-q", "-b", "main")
    (r / ".gitignore").write_text("config/\noutputs/\n", encoding="utf-8")
    (r / "config").mkdir()
    shutil.copyfile(ROOT / "config" / "leak_denylist.example.yaml", r / "config" / "leak_denylist.example.yaml")
    commit(r, {"README.txt": "clean\n"}, "initial")
    code, out = scan(r, "--tree-only", capsys=capsys)
    assert (r / "outputs" / "private" / "leak_denylist.yaml").exists()
    assert "created" in out and code == 0


def test_example_denylist_is_valid_and_fake():
    rules, excluded = leak_scan.load_denylist(ROOT / "config" / "leak_denylist.example.yaml")
    assert {r.name for r in rules} >= {"fake_client_names", "any_email", "claude_author"}
    assert excluded
