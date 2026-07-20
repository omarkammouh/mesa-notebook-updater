#!/usr/bin/env python3
"""Build the distributable .skill bundle (a zip) from skills/mesa-notebook-updater/.

Usage, from the repo root:

    python3 tools/package_skill.py            # -> dist/mesa-notebook-updater.skill
    python3 tools/package_skill.py --out PATH

The archive contains the skill folder as its single top-level directory
(mesa-notebook-updater/SKILL.md, ...), which is the layout claude.ai expects
when uploading a skill (Settings -> Capabilities -> Skills).
"""

import argparse
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "mesa-notebook-updater"
EXCLUDE_DIRS = {"__pycache__", ".ipynb_checkpoints"}
EXCLUDE_FILES = {".DS_Store"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=REPO / "dist" / "mesa-notebook-updater.skill")
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    files = [
        p
        for p in sorted(SKILL.rglob("*"))
        if p.is_file()
        and p.name not in EXCLUDE_FILES
        and not (set(p.parts) & EXCLUDE_DIRS)
    ]
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, Path(SKILL.name) / path.relative_to(SKILL))

    size = args.out.stat().st_size
    print(f"wrote {args.out} ({len(files)} files, {size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
