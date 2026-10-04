"""Preflight checks for /next, run before a task is picked. Owner: INT.

Each required check that fails stops the run and prints the exact fix. The gh check only warns.
If requirements.txt changed since the last install (or .last_install is missing), the install runs here
and the current commit is recorded in .last_install (gitignored).

Run with the project venv, which is the interpreter the install and the data load use:
    .venv\\Scripts\\python.exe scripts/preflight.py      (Windows)
    .venv/bin/python scripts/preflight.py               (macOS / Linux)

Exit code 0 when every required check passes; 1 when a check stops the run.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

from leaselens.config import data_dir, load_config, repo_root
from leaselens.contracts import SOURCE_FILES
from leaselens.io import load_raw

EXIT_OK = 0
EXIT_STOP = 1
VALID_TRACKS = ("INT", "MSR", "FCT")
MANIFEST_NAME = "manifest.json"
ZIP_HINT = "Unzip project-participants.zip into data/private/"
REQUIREMENTS = "requirements.txt"
REQUIREMENTS_WARNING = "**⚠️ REQUIREMENTS.TXT CHANGED — RUN `pip install -r requirements.txt` NOW**"
LAST_INSTALL = ".last_install"
SKIPPED_DIRS = {".git", ".venv", "venv", "node_modules"}

ROOT = repo_root()


def required_data_files() -> list[str]:
    """Names the sponsor package must contain in data/private/."""
    return [*SOURCE_FILES.values(), MANIFEST_NAME]


def missing_sources(names_present: set[str]) -> list[str]:
    """Required sponsor files that are not in the folder, in a stable order."""
    return [name for name in required_data_files() if name not in names_present]


def valid_track(text: str) -> bool:
    return text.strip() in VALID_TRACKS


def misplaced_env_files(relative_paths: list[str]) -> list[str]:
    """Paths of .env files that are not at the repository root (given as posix paths relative to the root)."""
    return [path for path in relative_paths if PurePosixPath(path).name == ".env" and path != ".env"]


def requirements_changed(stored_commit: str | None, changed_files: list[str]) -> bool:
    """True when there is no record of a previous install, or requirements.txt differs since that commit."""
    if stored_commit is None:
        return True
    return REQUIREMENTS in changed_files


def git(*args: str) -> tuple[int, str]:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace")
    return result.returncode, result.stdout.strip()


def check_track() -> tuple[bool, str]:
    path = ROOT / ".track"
    if not path.exists():
        return False, "Create the file .track at the repo root containing INT, MSR or FCT (it is gitignored)."
    if not valid_track(path.read_text(encoding="utf-8")):
        return False, "The file .track must contain exactly one word: INT, MSR or FCT."
    return True, f"track {path.read_text(encoding='utf-8').strip()}"


def worktree_action(status_output: str, branch: str) -> str:
    """'dirty' when anything is uncommitted (untracked files count), 'switch' when the clean tree is not on dev,
    otherwise 'ok'. A detached HEAD (empty branch name) counts as not on dev."""
    if status_output.strip():
        return "dirty"
    if branch.strip() != "dev":
        return "switch"
    return "ok"


def check_worktree() -> tuple[bool, str]:
    git("fetch", "--quiet", "origin")
    _, status = git("status", "--porcelain")
    _, branch = git("branch", "--show-current")
    action = worktree_action(status, branch)
    if action == "dirty":
        return False, "Uncommitted changes in the working tree. Commit or stash them yourself; nothing was discarded."
    if action == "switch":
        code, _ = git("switch", "dev")
        if code != 0:
            return False, "Could not switch to dev automatically. Run: git switch dev"
        print("switched to dev")
    _, counts = git("rev-list", "--left-right", "--count", "dev...origin/dev")
    ahead, behind = (int(part) for part in counts.split())
    if ahead:
        return False, "dev has commits that are not on origin/dev. Push them through a PR, or move them to a branch."
    if behind:
        code, _ = git("pull", "--ff-only", "--quiet")
        if code != 0:
            return False, "dev could not be fast-forwarded to origin/dev. Run: git pull, then fix the reported problem."
        print("pulled origin/dev")
    return True, "dev clean and up to date"


def check_real_data() -> tuple[bool, str]:
    folder = data_dir(load_config(mode="real"))
    present = {path.name for path in folder.iterdir()} if folder.is_dir() else set()
    missing = missing_sources(present)
    if missing:
        return False, f"{ZIP_HINT}. Missing: {', '.join(missing)}"
    try:
        load_raw(folder, verify=True)
    except Exception as error:  # the manifest check raises ValueError or OSError; only the type is printed
        return False, f"{ZIP_HINT}. The manifest check failed ({type(error).__name__}). Re-unzip the package."
    return True, "data/private verified against manifest.json"


def env_files_in_repo() -> list[str]:
    found = []
    for directory, subdirs, files in os.walk(ROOT):
        subdirs[:] = [name for name in subdirs if name not in SKIPPED_DIRS]
        for name in files:
            if name == ".env":
                found.append(Path(directory, name).relative_to(ROOT).as_posix())
    return found


def check_env() -> tuple[bool, str]:
    """Only the location and ignore status are checked. Contents are never read or printed."""
    found = env_files_in_repo()
    if not found:
        return True, "no .env file in the repository"
    misplaced = misplaced_env_files(found)
    if misplaced:
        moves = "; ".join(f"mv {path} .env" for path in misplaced)
        return False, f".env must be at the repo root (AGENTS.md §3.3). Move it: {moves}"
    code, _ = git("check-ignore", "-q", ".env")
    if code != 0:
        return False, ".env is not gitignored. Add '.env' to .gitignore."
    return True, ".env at the repo root and gitignored"


def check_gh() -> str | None:
    """A warning message when gh is unavailable or not logged in; None when it is fine."""
    if shutil.which("gh") is None:
        return "gh CLI not found: PRs will be printed as links. Run gh auth login once it is installed."
    result = subprocess.run(["gh", "auth", "status"], capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        return "gh is not logged in: run gh auth login (PRs will be printed as links until then)."
    return None


def check_requirements() -> tuple[bool, str]:
    last_path = ROOT / LAST_INSTALL
    stored = last_path.read_text(encoding="utf-8").strip() if last_path.exists() else None
    _, head = git("rev-parse", "HEAD")
    changed_files = []
    if stored:
        code, diff = git("diff", "--name-only", stored, head)
        if code != 0:
            stored = None  # the recorded commit is unknown to this clone, so treat it as never installed
        else:
            changed_files = diff.splitlines()
    if not requirements_changed(stored, changed_files):
        return True, "requirements.txt unchanged since the last install"
    print(REQUIREMENTS_WARNING)
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS], cwd=ROOT)
    if result.returncode != 0:
        return False, "pip install -r requirements.txt failed. Fix the error above and rerun preflight."
    last_path.write_text(head + "\n", encoding="utf-8")
    return True, "requirements installed; .last_install updated"


def configure_console() -> None:
    """Print UTF-8 with replacement, so the ⚠️ warning does not crash a Windows cp1252 console (REQUEST-MSR-02)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    configure_console()
    stops: list[str] = []
    passed: list[str] = []
    warnings: list[str] = []

    checks = [
        ("track", check_track),
        ("worktree", check_worktree),
        ("data", check_real_data),
        ("env", check_env),
        ("requirements", check_requirements),
    ]
    for name, check in checks:
        if name == "requirements" and stops:
            continue  # install only when everything else is fine, so a stopped run changes nothing
        ok, message = check()
        if ok:
            passed.append(f"{name}: {message}")
        else:
            stops.append(f"STOP [{name}] {message}")
            print(f"STOP [{name}] {message}")

    warning = check_gh()
    if warning:
        warnings.append(warning)
        print(f"WARN [gh] {warning}")

    if stops:
        print(f"PREFLIGHT: stopped ({len(stops)} check(s) failed)")
        return EXIT_STOP
    print(f"PREFLIGHT: ok — {'; '.join(passed)}" + (f" — warnings: {len(warnings)}" if warnings else ""))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
