#!/usr/bin/env python3
"""Build the distributable .skill bundle (a zip) from the repo root.

Usage, from the repo root:

    python3 tools/package_skill.py            # -> dist/mesa-notebook-updater.skill
    python3 tools/package_skill.py --out PATH

The skill lives at the repo root (SKILL.md, references/, scripts/), so the
bundle is built from an explicit include list rather than "everything here":
the repo scaffolding — evals/, tools/, .github/, README.md — is not part of the
skill and must not ship inside it.

The archive contains one top-level directory, mesa-notebook-updater/, which is
the layout claude.ai expects when uploading a skill (Settings -> Capabilities
-> Skills).
"""

import argparse
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_NAME = "mesa-notebook-updater"

# What the skill actually is. Everything else in the repo is scaffolding.
INCLUDE_FILES = ["SKILL.md", "CONTRIBUTING.md", "LICENSE"]
INCLUDE_DIRS = ["references", "scripts"]

EXCLUDE_DIRS = {"__pycache__", ".ipynb_checkpoints"}
EXCLUDE_FILES = {".DS_Store"}


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path,
                        default=REPO / "dist" / f"{SKILL_NAME}.skill")
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    files = collect()
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, Path(SKILL_NAME) / path.relative_to(REPO))

    size = args.out.stat().st_size
    print(f"wrote {args.out} ({len(files)} files, {size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
