#!/usr/bin/env python3
"""Build the distributable .skill bundle (a zip) from the repo root.

Usage, from the repo root:

    python3 tools/package_skill.py            # rebuild mesa-notebook-updater.skill
    python3 tools/package_skill.py --check    # verify it matches the sources
    python3 tools/package_skill.py --out PATH

The skill lives at the repo root (SKILL.md, references/, scripts/), so the
bundle is built from an explicit include list rather than "everything here":
the repo scaffolding — evals/, tools/, .github/, README.md — is not part of the
skill and must not ship inside it.

The archive contains one top-level directory, mesa-notebook-updater/, which is
the layout claude.ai expects when uploading a skill (Settings -> Capabilities
-> Skills).

The bundle is committed to the repository so that collaborators can download a
ready-to-upload file without building anything, which means it can go stale
against the sources. Two things stop that: the build is byte-for-byte
deterministic (fixed timestamps and permissions, sorted entries), so rebuilding
an unchanged tree produces an identical file and git shows no diff; and
`--check` rebuilds into a temporary file and compares, which CI runs on every
push. If you change SKILL.md, references/ or scripts/, rerun this script and
commit the result alongside.
"""

import argparse
import hashlib
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_NAME = "mesa-notebook-updater"
BUNDLE = REPO / f"{SKILL_NAME}.skill"

# What the skill actually is. Everything else in the repo is scaffolding.
INCLUDE_FILES = ["SKILL.md", "CONTRIBUTING.md", "LICENSE"]
INCLUDE_DIRS = ["references", "scripts"]

EXCLUDE_DIRS = {"__pycache__", ".ipynb_checkpoints"}
EXCLUDE_FILES = {".DS_Store"}

# Fixed metadata so the archive is reproducible. The date is the zip epoch;
# any constant would do, but it must never come from the filesystem.
ZIP_DATE = (1980, 1, 1, 0, 0, 0)
FILE_MODE = 0o644 << 16


def collect() -> list:
    files = []
    for name in INCLUDE_FILES:
        path = REPO / name
        if not path.is_file():
            sys.exit(f"FAIL: {name} is missing from the repo root")
        files.append(path)
    for name in INCLUDE_DIRS:
        root = REPO / name
        if not root.is_dir():
            sys.exit(f"FAIL: {name}/ is missing from the repo root")
        files += [
            p
            for p in sorted(root.rglob("*"))
            if p.is_file()
            and p.name not in EXCLUDE_FILES
            and not (set(p.parts) & EXCLUDE_DIRS)
        ]
    return files


def build(out: Path, files: list) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            arcname = str(Path(SKILL_NAME) / path.relative_to(REPO))
            info = zipfile.ZipInfo(arcname, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = FILE_MODE
            zf.writestr(info, path.read_bytes())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=BUNDLE)
    parser.add_argument("--check", action="store_true",
                        help="verify the committed bundle matches the sources")
    args = parser.parse_args()

    files = collect()

    if args.check:
        if not args.out.is_file():
            print(f"FAIL: {args.out.name} is not in the repository — "
                  "run: python3 tools/package_skill.py", file=sys.stderr)
            return 1
        with tempfile.TemporaryDirectory() as tmp:
            fresh = Path(tmp) / "fresh.skill"
            build(fresh, files)
            if digest(fresh) != digest(args.out):
                print(f"FAIL: {args.out.name} is stale — it does not match "
                      "SKILL.md / references/ / scripts/.\n"
                      "run: python3 tools/package_skill.py, then commit it",
                      file=sys.stderr)
                return 1
        print(f"ok  {args.out.name} matches the sources ({len(files)} files)")
        return 0

    build(args.out, files)
    size = args.out.stat().st_size
    print(f"wrote {args.out} ({len(files)} files, {size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
