"""Leak scanner: look for denylisted terms in the working tree and in git history.

Scans (a) tracked files of the working tree and (b) the full history
(``git log -p --all``, commit messages, author and committer names and emails).

The denylist lives in ``outputs/private/leak_denylist.yaml`` (gitignored, never
committed). If it is missing it is created from ``config/leak_denylist.example.yaml``.

Output is deliberately blind: per rule it prints counts, file paths and short commit
hashes only. The text that matched is never printed and never written to disk.

Usage::

    python scripts/leak_scan.py                 # tree + history, exit 1 if anything is found
    python scripts/leak_scan.py --tree-only     # tracked files only
    python scripts/leak_scan.py --baseline      # write counts to outputs/private/leak_baseline.json, exit 0

Denylist format (YAML; the PyYAML package is already a project dependency)::

    excluded_paths: [glob, ...]        # skipped entirely in the tree scan
    special_checks:                    # optional; every check is on by default
      any_email: {enabled: true, allowed_paths: [glob], allowed_emails: [address]}
      coauthored_trailer: {enabled: true, allowed_paths: []}
      claude_author: {enabled: true, allowed_paths: []}
      generated_with: {enabled: true, allowed_paths: []}
    rules:
      - name: some_rule_name           # printed in reports, so keep it neutral
        type: literal | regex          # literal = case-insensitive substring
        patterns: [...]
        ignore_case: false             # regex only; literals are always case-insensitive
        allowed_paths: [glob, ...]     # matches here are tolerated

Globs use fnmatch semantics where ``*`` also crosses ``/``; ``dir/**`` matches everything below ``dir``.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DENYLIST_RELPATH = "outputs/private/leak_denylist.yaml"
EXAMPLE_RELPATH = "config/leak_denylist.example.yaml"
BASELINE_RELPATH = "outputs/private/leak_baseline.json"

HISTORY_MESSAGE_PATH = "<commit-message>"
HISTORY_META_PATH = "<commit-metadata>"
BINARY_SNIFF_BYTES = 8192
COMMIT_MARK = "\x01COMMIT\x01"
META_SEP = "\x1f"
META_END = "\x1e"

SPECIAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "any_email": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+"),
    "coauthored_trailer": re.compile(r"co-authored-by\s*:", re.IGNORECASE),
    "generated_with": re.compile(r"generated with", re.IGNORECASE),
}
CLAUDE_AUTHOR = re.compile(r"claude", re.IGNORECASE)


@dataclass
class Rule:
    """One scanning rule: compiled matcher plus the paths where hits are tolerated."""

    name: str
    matchers: list[re.Pattern[str]]
    allowed_paths: list[str] = field(default_factory=list)
    allowed_emails: set[str] = field(default_factory=set)
    meta_only: bool = False  # claude_author applies to names, not to file content


@dataclass
class Findings:
    """Hits per rule: line counts, affected paths and short commit hashes (never the text)."""

    counts: dict[str, int] = field(default_factory=dict)
    paths: dict[str, set[str]] = field(default_factory=dict)
    commits: dict[str, set[str]] = field(default_factory=dict)

    def add(self, rule: str, path: str, commit: str | None) -> None:
        self.counts[rule] = self.counts.get(rule, 0) + 1
        self.paths.setdefault(rule, set()).add(path)
        if commit:
            self.commits.setdefault(rule, set()).add(commit)

    def total(self) -> int:
        return sum(self.counts.values())


def _git(repo: Path, *args: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(["git", "-C", str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _git_text(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)
    return out.stdout.decode("utf-8", errors="replace")


def glob_match(path: str, patterns: list[str]) -> bool:
    """True if ``path`` matches any glob; ``dir/**`` matches the whole subtree."""
    for pat in patterns:
        if fnmatch.fnmatchcase(path, pat):
            return True
        if pat.endswith("/**") and path.startswith(pat[:-2]):
            return True
        if pat.endswith("/**") and path == pat[:-3]:
            return True
    return False


def load_denylist(path: Path) -> tuple[list[Rule], list[str]]:
    """Parse the denylist file into rules (user rules + enabled special checks) and excluded paths."""
    import yaml  # PyYAML is a project dependency; imported lazily so --help works without it

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    excluded = [str(p) for p in data.get("excluded_paths", []) or []]
    rules: list[Rule] = []
    for raw in data.get("rules", []) or []:
        kind = raw.get("type", "literal")
        patterns = [str(p) for p in raw.get("patterns", [])]
        if kind == "literal":
            matchers = [re.compile(re.escape(p), re.IGNORECASE) for p in patterns]
        elif kind == "regex":
            flags = re.IGNORECASE if raw.get("ignore_case", False) else 0
            matchers = [re.compile(p, flags) for p in patterns]
        else:
            raise ValueError(f"rule {raw.get('name')!r}: unknown type {kind!r}")
        rules.append(Rule(str(raw["name"]), matchers, [str(p) for p in raw.get("allowed_paths", []) or []]))
    special = data.get("special_checks", {}) or {}
    for name in [*SPECIAL_PATTERNS, "claude_author"]:
        cfg = special.get(name, {}) or {}
        if not cfg.get("enabled", True):
            continue
        matcher = CLAUDE_AUTHOR if name == "claude_author" else SPECIAL_PATTERNS[name]
        rules.append(
            Rule(
                name,
                [matcher],
                [str(p) for p in cfg.get("allowed_paths", []) or []],
                {str(e).lower() for e in cfg.get("allowed_emails", []) or []},
                meta_only=name == "claude_author",
            )
        )
    return rules, excluded


def ensure_denylist(repo: Path, denylist: Path) -> bool:
    """Create the private denylist from the committed example if missing. Returns True if created."""
    if denylist.exists():
        return False
    example = repo / EXAMPLE_RELPATH
    denylist.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example, denylist)
    return True


def _line_hits(rule: Rule, line: str) -> bool:
    for matcher in rule.matchers:
        for m in matcher.finditer(line):
            if rule.name == "any_email" and m.group(0).lower() in rule.allowed_emails:
                continue
            return True
    return False


def scan_text(text: str, path: str, rules: list[Rule], findings: Findings, commit: str | None) -> None:
    """Scan a block of text line by line; record one hit per matching line per rule."""
    applicable = [r for r in rules if not r.meta_only and not glob_match(path, r.allowed_paths)]
    for line in text.splitlines():
        for rule in applicable:
            if _line_hits(rule, line):
                findings.add(rule.name, path, commit)


def scan_tree(repo: Path, rules: list[Rule], excluded: list[str]) -> Findings:
    """Scan every tracked file of the working tree (binary files and excluded paths are skipped)."""
    findings = Findings()
    for rel in _git_text(repo, "ls-files", "-z").split("\x00"):
        if not rel or glob_match(rel, excluded):
            continue
        file = repo / rel
        if not file.is_file():
            continue
        raw = file.read_bytes()
        if b"\x00" in raw[:BINARY_SNIFF_BYTES]:
            continue
        scan_text(raw.decode("utf-8", errors="replace"), rel, rules, findings, None)
    return findings


def _scan_meta(rules: list[Rule], meta: list[str], message: str, short: str, findings: Findings) -> None:
    names = " ".join(meta[0:1] + meta[2:3])  # author name, committer name
    meta_text = "\n".join(meta)
    for rule in rules:
        if glob_match(HISTORY_META_PATH, rule.allowed_paths):
            continue
        if rule.meta_only:
            if any(m.search(names) for m in rule.matchers):
                findings.add(rule.name, HISTORY_META_PATH, short)
        elif _line_hits(rule, meta_text.replace("\n", " ")):
            findings.add(rule.name, HISTORY_META_PATH, short)
    scan_text(message, HISTORY_MESSAGE_PATH, rules, findings, short)


def scan_history(repo: Path, rules: list[Rule]) -> Findings:
    """Scan commit messages, author/committer fields and every added or removed diff line of all refs."""
    findings = Findings()
    fmt = f"{COMMIT_MARK}%h{META_SEP}%an{META_SEP}%ae{META_SEP}%cn{META_SEP}%ce{META_SEP}%B{META_END}"
    proc = _git(repo, "log", "--all", "-p", "-U0", "--no-color", "--no-ext-diff", f"--format={fmt}")
    assert proc.stdout is not None
    commit = ""
    path = ""
    in_header = False
    header_buf: list[str] = []
    for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace")
        if in_header:
            header_buf.append(line)
            if META_END in line:
                blob = "".join(header_buf).split(META_END, 1)[0]
                parts = blob.split(META_SEP, 5)
                if len(parts) == 6:
                    _scan_meta(rules, parts[1:5], parts[5], commit, findings)
                in_header = False
                header_buf = []
            continue
        if line.startswith(COMMIT_MARK):
            rest = line[len(COMMIT_MARK):]
            commit = rest.split(META_SEP, 1)[0]
            header_buf = [rest]
            if META_END in rest:
                blob = rest.split(META_END, 1)[0]
                parts = blob.split(META_SEP, 5)
                if len(parts) == 6:
                    _scan_meta(rules, parts[1:5], parts[5], commit, findings)
                header_buf = []
            else:
                in_header = True
            continue
        if line.startswith("diff --git "):
            path = line.rstrip("\n").rsplit(" b/", 1)[-1]
            continue
        if (line.startswith("+") and not line.startswith("+++ ")) or (line.startswith("-") and not line.startswith("--- ")):
            scan_text(line[1:], path, rules, findings, commit)
    proc.wait()
    return findings


def render(title: str, findings: Findings) -> str:
    """Counts, paths and short hashes per rule. Never any matched text."""
    lines = [f"== {title}: {findings.total()} hit line(s) in {len(findings.counts)} rule(s) =="]
    for rule in sorted(findings.counts):
        lines.append(f"[{rule}] hit lines: {findings.counts[rule]}")
        paths = sorted(findings.paths.get(rule, ()))
        if paths:
            lines.append(f"  paths ({len(paths)}): " + ", ".join(paths))
        commits = sorted(findings.commits.get(rule, ()))
        if commits:
            lines.append(f"  commits ({len(commits)}): " + ", ".join(commits))
    return "\n".join(lines)


def summary(findings: Findings) -> dict[str, dict[str, int]]:
    """Machine-readable counts (no text, no paths)."""
    return {
        rule: {
            "hit_lines": findings.counts[rule],
            "paths": len(findings.paths.get(rule, ())),
            "commits": len(findings.commits.get(rule, ())),
        }
        for rule in sorted(findings.counts)
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tree-only", action="store_true", help="scan tracked files only, skip git history")
    parser.add_argument("--baseline", action="store_true", help=f"write counts to {BASELINE_RELPATH} and exit 0")
    parser.add_argument("--repo", type=Path, default=None, help="repository root (default: git top level of cwd)")
    parser.add_argument("--denylist", type=Path, default=None, help=f"denylist file (default: {DENYLIST_RELPATH})")
    args = parser.parse_args(argv)

    repo = args.repo or Path(_git_text(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    denylist = args.denylist or repo / DENYLIST_RELPATH
    if ensure_denylist(repo, denylist):
        print(f"denylist missing: created {denylist.relative_to(repo) if denylist.is_relative_to(repo) else denylist} from the example (fake terms)")
    rules, excluded = load_denylist(denylist)

    tree = scan_tree(repo, rules, excluded)
    print(render("working tree", tree))
    history: Findings | None = None
    if not args.tree_only:
        history = scan_history(repo, rules)
        print(render("git history", history))

    if args.baseline:
        out = repo / BASELINE_RELPATH
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"tree": summary(tree), "history": summary(history) if history else None}
        out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"baseline written to {BASELINE_RELPATH}")
        return 0
    found = tree.total() + (history.total() if history else 0)
    print("RESULT: clean" if not found else f"RESULT: {found} hit line(s) found")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
