"""Block direct pushes to main and dev. Owner: INT.

Runs as a pre-commit hook at the pre-push stage (see .pre-commit-config.yaml).
pre-commit sets PRE_COMMIT_REMOTE_BRANCH to the branch being pushed to, e.g. "refs/heads/dev".
Work goes on feature branches (int/, msr/, fct/) and reaches dev through pull requests only.
"""

import os
import sys

PROTECTED_BRANCHES = {"refs/heads/main", "refs/heads/dev"}


def main() -> int:
    target = os.environ.get("PRE_COMMIT_REMOTE_BRANCH", "")
    if target in PROTECTED_BRANCHES:
        name = target.removeprefix("refs/heads/")
        print(f"\nBLOCKED: direct push to '{name}' is not allowed.")
        print("Push your feature branch instead and open a pull request into dev.\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
