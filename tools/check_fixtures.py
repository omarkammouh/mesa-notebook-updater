#!/usr/bin/env python3
"""Regression smoke test: the scanner must catch every planted finding.

For each eval fixture in evals/inputs/, the answer key in
evals/expected/<name>.manifest.json lists the findings that were deliberately
planted in the notebook (`planted_findings`, each with an `api_id`). This
script runs the target-conditioned scanner on every input and fails if any
registry-backed planted api_id is no longer reported at ANY target on the
ladder — i.e. if a registry or scanner change opened a hole in the "nothing
gets missed" guarantee.

Two planted-finding kinds, by design:
  - api_id present in references/api-registry.json  -> must be regex-caught.
    Status is a function of the target, and some entries are deliberately
    suppressed at targets where the idiom is current (their concern is the
    other migration direction), so each fixture is scanned at several targets
    and the finding must surface at at least one.
  - api_id absent from the registry (e.g. run-loop, manual-agent-creation) ->
    a SEMANTIC judge item: caught by the SKILL.md Step 5 modernization
    checklist, not by regex. Skipped here; the agent-run evals grade those.

Stdlib only. Run from the repo root:

    python3 tools/check_fixtures.py
"""

import json
import subprocess
import sys
from pathlib import Path

# Each fixture is scanned at every target on this ladder; a planted finding
# passes if it surfaces at at least one. The ladder spans both migration
# directions: the latest stable at fixture-build time (upgrade direction),
# a mid-3.x pin, and a 2.x target (downgrade/anachronism direction). Extend it
# together with the fixtures/manifests, not on its own.
TARGET_LADDER = ["3.5.1", "3.3.0", "2.4.0"]

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO           # the skill lives at the repo root
SCANNER = SKILL / "scripts" / "scan_notebook.py"
INPUTS = REPO / "evals" / "inputs"
EXPECTED = REPO / "evals" / "expected"


def registry_ids() -> set:
    registry = json.loads((SKILL / "references" / "api-registry.json").read_text())
    entries = registry["entries"] if isinstance(registry, dict) else registry
    return {e["id"] for e in entries}


def scan(notebook: Path, target: str) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCANNER),
            "--target",
            target,
            "--registry",
            str(SKILL / "references" / "api-registry.json"),
            "--catalog",
            str(SKILL / "references" / "version-catalog.json"),
            "--json",
            # Planted findings in modern-era fixtures are CURRENT idioms the
            # scanner must still recognize (era evidence / downgrade work
            # list), so include matched-but-current entries in the report.
            "--show-current",
            str(notebook),
        ],
        capture_output=True,
        text=True,
    )
    # The scanner exits non-zero when it finds actionable items — that is the
    # expected outcome for most fixtures, so only a missing/invalid report is
    # an error here.
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"scanner produced no JSON for {notebook.name} at target {target}\n"
            f"stdout: {proc.stdout[:500]}\nstderr: {proc.stderr[:500]}"
        )


def main() -> int:
    failures = []
    checked = semantic = 0
    known_ids = registry_ids()
    manifests = sorted(EXPECTED.glob("*.manifest.json"))
    if not manifests:
        print("no manifests found under evals/expected/", file=sys.stderr)
        return 1

    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text())
        fixture = manifest["fixture"]
        if not fixture.endswith(".ipynb"):  # some manifests omit the suffix
            fixture += ".ipynb"
        notebook = INPUTS / fixture
        if not notebook.exists():
            failures.append(f"{manifest_path.name}: fixture {fixture} missing")
            continue

        reported = set()
        for target in TARGET_LADDER:
            reported |= set(scan(notebook, target).get("summary", {}).get("by_api", {}))

        planted = [f["api_id"] for f in manifest.get("planted_findings", [])]
        regex_backed = [api for api in planted if api in known_ids]
        semantic += len(planted) - len(regex_backed)
        checked += len(regex_backed)
        missed = [api for api in regex_backed if api not in reported]

        status = "ok" if not missed else "MISS"
        print(
            f"[{status}] {fixture:32s} planted={len(planted):2d} "
            f"regex-backed={len(regex_backed):2d} reported_apis={len(reported):2d}"
        )
        for api in missed:
            failures.append(f"{fixture}: planted finding not reported at any target: {api}")

    print(
        f"\n{len(manifests)} fixtures; {checked} regex-backed planted findings checked "
        f"across targets {', '.join(TARGET_LADDER)}; "
        f"{semantic} semantic judge items left to the agent-run evals."
    )
    if failures:
        print("\nFAILURES:")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("All regex-backed planted findings are still caught by the scanner.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
