"""Compute task status for the three boards from git, and suggest the next task. Owner: INT.

Status is never stored in the boards; it is derived:
  done       one of these holds:
             - a commit SUBJECT on origin/dev contains "[<TRACK>][<ID>]" with the task's own track
               (direct commit or squash-merge title, e.g. "[MSR][M-02] Add build_pairs")
             - a commit SUBJECT on origin/dev contains "/<prefix><ID>-" with the task's own prefix
               (GitHub merge subject, e.g. "Merge pull request #5 from owner/msr/M-02-pairs")
             - the row's Notes start with "done"
             Commit bodies are ignored. Word boundaries apply: I-01 never matches I-01b or I-010.
  in-review  a remote branch <prefix><ID>-... exists and the task is not done
  todo       otherwise
A task is workable when every dependency is done. "continuous" tasks are never picked.
Among workable tasks, a row whose Notes start with "priority" is picked first; board order breaks ties.

Usage:
  python scripts/board_status.py                 # all tracks
  python scripts/board_status.py --track MSR     # one track + its next task
  python scripts/board_status.py --no-fetch      # skip git fetch (offline)
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACKS = {"INT": "int/", "MSR": "msr/", "FCT": "fct/"}
BOARD_ROW = re.compile(r"^\|\s*([IMF]-\d+[a-z]?)\s*\|(.*)\|\s*$")
PRIORITY_MARK = "priority"  # a workable row whose Notes start with this is picked before other workable rows
RECORD_SEPARATOR = "\x1e"  # ends each commit in the `git log --format=%B%x1e` dump


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def read_board(track: str) -> list[dict]:
    rows = []
    for line in (ROOT / "docs" / "board" / f"{track}.md").read_text(encoding="utf-8").splitlines():
        match = BOARD_ROW.match(line)
        if not match:
            continue
        cells = [cell.strip() for cell in match.group(2).split("|")]
        task, depends, notes = (cells + ["", "", ""])[:3]
        deps = [d.strip() for d in re.split(r"[,\s]+", depends) if re.match(r"^[IMF]-\d+[a-z]?$", d.strip())]
        rows.append({"id": match.group(1), "task": task, "depends": deps, "raw_depends": depends,
                     "notes": notes, "track": track})
    return rows


def subject_lines(raw_log: str) -> list[str]:
    """First line of each commit message in a `git log --format=%B%x1e` dump. Bodies are dropped."""
    subjects = []
    for message in raw_log.split(RECORD_SEPARATOR):
        lines = [line.strip() for line in message.splitlines() if line.strip()]
        if lines:
            subjects.append(lines[0])
    return subjects


def is_done(task_id: str, track: str, notes: str, subjects: list[str]) -> bool:
    """True when the task's own track tag or branch prefix appears in a commit subject, or Notes say done.

    The trailing "]" and "-" keep IDs apart: "[INT][I-12]" does not match "[INT][I-12a]", and
    "/msr/M-02-" does not match "/msr/M-020-" or "/msr/M-01-".
    """
    if notes.strip().lower().startswith("done"):
        return True
    tag = f"[{track}][{task_id}]"
    branch = f"/{TRACKS[track]}{task_id}-"
    return any(tag in subject or branch in subject for subject in subjects)


def compute(fetch: bool = True) -> dict[str, list[dict]]:
    if fetch:
        git("fetch", "--quiet", "origin")
    subjects = subject_lines(git("log", "origin/dev", f"--format=%B{RECORD_SEPARATOR}"))
    remote_branches = [b.strip().removeprefix("origin/") for b in git("branch", "-r").splitlines()]
    boards = {track: read_board(track) for track in TRACKS}
    for track, rows in boards.items():
        for row in rows:
            if is_done(row["id"], track, row["notes"], subjects):
                row["status"] = "done"
            elif any(b.startswith(TRACKS[track] + row["id"] + "-") for b in remote_branches):
                row["status"] = "in-review"
            else:
                row["status"] = "todo"
    status_by_id = {row["id"]: row["status"] for rows in boards.values() for row in rows}
    for rows in boards.values():
        for row in rows:
            row["waiting_on"] = [d for d in row["depends"] if status_by_id.get(d) != "done"]
            row["continuous"] = "continuous" in row["notes"].lower()
            open_dependency_text = "all core tasks" in row["raw_depends"]
            row["workable"] = (row["status"] == "todo" and not row["continuous"]
                               and not row["waiting_on"] and not open_dependency_text)
    return boards


def is_priority(row: dict) -> bool:
    """True when the row's Notes start with "priority" (case-insensitive)."""
    return row["notes"].strip().lower().startswith(PRIORITY_MARK)


def next_task(rows: list[dict]) -> tuple[dict | None, dict | None]:
    """First workable task, and first task blocked only by other tracks (workable on synthetic data).

    A workable row marked "priority" beats every other workable row; board order breaks ties.
    """
    workable_rows = [r for r in rows if r["workable"]]
    priority_rows = [r for r in workable_rows if is_priority(r)]
    workable = next(iter(priority_rows or workable_rows), None)
    own_prefix = rows[0]["id"][0] if rows else ""
    synthetic = next((r for r in rows if r["status"] == "todo" and not r["continuous"] and r["waiting_on"]
                      and all(not d.startswith(own_prefix) for d in r["waiting_on"])), None)
    return workable, synthetic


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--track", choices=list(TRACKS))
    parser.add_argument("--no-fetch", action="store_true")
    args = parser.parse_args()
    boards = compute(fetch=not args.no_fetch)
    tracks = [args.track] if args.track else list(TRACKS)
    for track in tracks:
        rows = boards[track]
        counts = {s: sum(r["status"] == s for r in rows) for s in ("done", "in-review", "todo")}
        print(f"\n{track}: {counts['done']} done · {counts['in-review']} in review · {counts['todo']} todo")
        for r in rows:
            wait = f"  (waiting on {', '.join(r['waiting_on'])})" if r["waiting_on"] and r["status"] == "todo" else ""
            print(f"  {r['id']:<6} {r['status']:<10} {r['task'][:60]}{wait}")
        workable, synthetic = next_task(rows)
        if workable:
            print(f"NEXT {track}: {workable['id']} — {workable['task']}")
        elif synthetic:
            print(f"NEXT {track} (synthetic until deps merge): {synthetic['id']} — waiting on "
                  f"{', '.join(synthetic['waiting_on'])}")
        else:
            print(f"NEXT {track}: nothing workable right now")


if __name__ == "__main__":
    main()
