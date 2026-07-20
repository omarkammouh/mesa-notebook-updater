#!/usr/bin/env python3
"""Structural validation of the packaged skill. Stdlib only.

Checks, from the repo root (python3 tools/validate_skill.py):

  1. SKILL.md has YAML frontmatter with `name` and `description`, and the
     name matches the skill folder name.
  2. Both reference JSON files parse, and every registry regex compiles.
  3. Every registry lifecycle stamp is a real version string (delegates to
     mesa_versions.validate_lifecycle) and the lifecycle self-test passes.
  4. Every version referenced by a registry stamp exists in the catalog.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "mesa-notebook-updater"

sys.path.insert(0, str(SKILL / "scripts"))
import mesa_versions  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check_frontmatter() -> None:
    text = (SKILL / "SKILL.md").read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        fail("SKILL.md has no YAML frontmatter")
    front = match.group(1)
    name = re.search(r"^name:\s*(\S+)", front, re.MULTILINE)
    if not name:
        fail("SKILL.md frontmatter missing `name`")
    if name.group(1) != SKILL.name:
        fail(f"frontmatter name {name.group(1)!r} != folder name {SKILL.name!r}")
    if not re.search(r"^description:", front, re.MULTILINE):
        fail("SKILL.md frontmatter missing `description`")
    print("ok  SKILL.md frontmatter (name, description)")


def check_registry() -> dict:
    registry = json.loads((SKILL / "references" / "api-registry.json").read_text())
    entries = registry["entries"] if isinstance(registry, dict) else registry
    ids = set()
    for entry in entries:
        eid = entry.get("id")
        if not eid:
            fail(f"registry entry without id: {str(entry)[:80]}")
        if eid in ids:
            fail(f"duplicate registry id: {eid}")
        ids.add(eid)
        for pattern in entry.get("patterns", []):
            try:
                re.compile(pattern)
            except re.error as exc:
                fail(f"registry {eid}: regex does not compile: {pattern!r} ({exc})")
        try:
            mesa_versions.validate_lifecycle(entry)
        except Exception as exc:
            fail(f"registry {eid}: bad lifecycle stamp: {exc}")
    print(f"ok  api-registry.json ({len(entries)} entries, all regexes compile, stamps valid)")
    return entries


def check_catalog(entries) -> None:
    catalog = json.loads((SKILL / "references" / "version-catalog.json").read_text())
    releases = {r["version"] for r in catalog["releases"]}
    print(f"ok  version-catalog.json ({len(releases)} releases)")

    known = {mesa_versions.parse_version(v) for v in releases}
    for entry in entries:
        for field in ("introduced", "deprecated", "superseded", "removed"):
            stamp = entry.get(field)
            if stamp and mesa_versions.parse_version(stamp) not in known:
                fail(
                    f"registry {entry['id']}: {field}={stamp} not in catalog "
                    "(add the release or fix the stamp)"
                )
    print("ok  every registry stamp resolves to a catalog release")


def check_selftest() -> None:
    proc = subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "mesa_versions.py")],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        fail(f"mesa_versions.py self-test failed:\n{proc.stdout}\n{proc.stderr}")
    print("ok  mesa_versions.py lifecycle self-test")


def main() -> None:
    check_frontmatter()
    entries = check_registry()
    check_catalog(entries)
    check_selftest()
    print("\nSkill structure valid.")


if __name__ == "__main__":
    main()
