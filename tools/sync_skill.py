#!/usr/bin/env python3
"""Keep the repo's copy of the skill identical to the installed one.

The skill is edited in place at ~/.claude/skills/mesa-notebook-updater/ (that
copy is the one Claude actually loads, so it is where the work happens). The
copy under skills/ in this repo is a mirror of it. Mirrors go stale silently,
so this script compares them and can refresh the repo copy.

    python3 tools/sync_skill.py            # report drift, exit 1 if any
    python3 tools/sync_skill.py --apply    # copy installed -> repo, then report

The direction is always installed -> repo. Never the reverse: the repo copy is
generated, and copying it back would overwrite work in the live skill.

If the skill is not installed on this machine the script exits 0 without doing
anything, so contributors who only have the repo are unaffected (and so the
pre-commit hook stays harmless for them).
"""

import argparse
import filecmp
import hashlib
import shutil
import sys
from pathlib import Path

SKILL_NAME = "mesa-notebook-updater"
REPO = Path(__file__).resolve().parent.parent
REPO_SKILL = REPO / "skills" / SKILL_NAME
DEFAULT_INSTALLED = Path.home() / ".claude" / "skills" / SKILL_NAME

IGNORE_DIRS = {"__pycache__", ".ipynb_checkpoints"}
IGNORE_FILES = {".DS_Store"}


def tree(root: Path) -> dict:
    """Map relative path -> sha256, skipping generated junk."""
    out = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in IGNORE_FILES or set(path.parts) & IGNORE_DIRS:
            continue
        rel = path.relative_to(root)
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def compare(installed: Path, repo: Path):
    a, b = tree(installed), tree(repo)
    missing = sorted(set(a) - set(b))        # in installed, not in repo
    extra = sorted(set(b) - set(a))          # in repo, not in installed
    changed = sorted(p for p in set(a) & set(b) if a[p] != b[p])
    return missing, extra, changed


def apply_sync(installed: Path, repo: Path) -> None:
    """Mirror installed onto repo: copy new/changed, delete removed."""
    a, b = tree(installed), tree(repo)
    for rel in sorted(set(a) - set(b)) + sorted(p for p in set(a) & set(b) if a[p] != b[p]):
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(installed / rel, dest)
        print(f"  copied  {rel}")
    for rel in sorted(set(b) - set(a)):
        (repo / rel).unlink()
        print(f"  deleted {rel}")
    # drop directories the deletions emptied
    for path in sorted(repo.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="refresh the repo copy from the installed one")
    parser.add_argument("--installed", type=Path, default=DEFAULT_INSTALLED,
                        help=f"path to the installed skill (default: {DEFAULT_INSTALLED})")
    args = parser.parse_args()

    if not args.installed.is_dir():
        print(f"no installed skill at {args.installed} — nothing to compare")
        return 0
    if not REPO_SKILL.is_dir():
        print(f"FAIL: repo copy missing at {REPO_SKILL}", file=sys.stderr)
        return 1

    if args.apply:
        print(f"syncing {args.installed} -> {REPO_SKILL}")
        apply_sync(args.installed, REPO_SKILL)

    missing, extra, changed = compare(args.installed, REPO_SKILL)
    if not (missing or extra or changed):
        print(f"in sync: repo copy matches {args.installed}")
        return 0

    print("OUT OF SYNC — the repo copy does not match the installed skill:")
    for rel in missing:
        print(f"  only in installed : {rel}")
    for rel in extra:
        print(f"  only in repo      : {rel}")
    for rel in changed:
        print(f"  differs           : {rel}")
    print("\nrun: python3 tools/sync_skill.py --apply")
    return 1


if __name__ == "__main__":
    sys.exit(main())
