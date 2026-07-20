#!/usr/bin/env python3
"""Regenerate references/version-catalog.json from PyPI (+ optional HISTORY.md).

Mechanical fields (date, requires_python, prerelease, yanked, on_pypi,
installable) come from the PyPI JSON API and are always refreshed. Curated
fields (python_pin, install, band, highlights, breaking, deprecations,
additions) are seeded from the CURATION table embedded below on first run and
are PRESERVED from the existing catalog on subsequent runs — hand edits win.

Run (maintainer, when Mesa releases a new version):
    uv run --with nothing python scripts/update_catalog.py            # uses network
    python scripts/update_catalog.py --pypi-json /path/to/pypi.json   # offline

Then curate the "needs curation" versions it prints, append the narrative
section to version-history.md, and stamp api-registry.json lifecycle fields.

Stdlib only. Python 3.9+.
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesa_versions import parse_version  # noqa: E402

CATALOG = Path(__file__).resolve().parent.parent / "references" / "version-catalog.json"
PYPI_URL = "https://pypi.org/pypi/mesa/json"
HISTORY_URL = "https://raw.githubusercontent.com/mesa/mesa/main/HISTORY.md"

# GitHub-only ghost releases (in changelog/tags but never uploaded to PyPI).
GHOSTS = [
    {"version": "2.0.0", "date": "2023-07-15", "on_pypi": False, "installable": False,
     "band": "2.1-2.4", "python_pin": "3.11", "install": None,
     "note": "Codename Wellton; announced but never uploaded to PyPI — invalid "
             "target. Nearest installable: 2.1."},
]

# ---------------------------------------------------------------------------
# Curated knowledge. Keyed by exact PyPI version. Seeds the catalog; once
# written, the catalog's own values are preserved and these act only as a
# fallback for versions not yet in the catalog. Coverage: full for 2.1+,
# coarse below. Sources: PyPI, HISTORY.md (3.0+), the migration guide (2.x).
# ---------------------------------------------------------------------------
CURATION = {
    "2.1":   {"band": "2.1-2.4", "highlights": ["Mesa 2.1 line: schedulers (mesa.time), mesa.space grids, ModularServer visualization"]},
    "2.1.1": {"band": "2.1-2.4"}, "2.1.2": {"band": "2.1-2.4"}, "2.1.3": {"band": "2.1-2.4"},
    "2.1.4": {"band": "2.1-2.4"}, "2.1.5": {"band": "2.1-2.4"},
    "2.2.0": {"band": "2.1-2.4", "highlights": ["AgentSet introduced (model.agents); schedulers still primary"]},
    "2.2.1": {"band": "2.1-2.4"}, "2.2.2": {"band": "2.1-2.4"}, "2.2.3": {"band": "2.1-2.4"}, "2.2.4": {"band": "2.1-2.4"},
    "2.3.0": {"band": "2.1-2.4",
              "highlights": ["Experimental SolaraViz/JupyterViz added; scheduler-deprecation groundwork"],
              "additions": ["SolaraViz (experimental)", "JupyterViz (experimental)"]},
    "2.3.1": {"band": "2.1-2.4"}, "2.3.2": {"band": "2.1-2.4"}, "2.3.3": {"band": "2.1-2.4"},
    "2.3.4": {"band": "2.1-2.4", "highlights": ["Last 2.3.x; deprecation warnings for schedulers/old idioms"]},
    "2.4.0": {"band": "2.1-2.4", "highlights": ["Final Mesa 2.x release before the 3.0 break"]},
    "3.0.0": {"band": "3.0",
              "highlights": ["Mandatory super().__init__(); automatic unique_id; schedulers deprecated (AgentSet replaces them); SolaraViz; agenttype_reporters; mesa.flat removed"],
              "breaking": ["automatic unique_id (no unique_id arg to Agent)", "mesa.flat namespace removed", "old ModularServer visualization removed"],
              "deprecations": ["mesa.time schedulers (RandomActivation etc.)"],
              "additions": ["AgentSet (select/groupby/agg/do/shuffle_do)", "SolaraViz + make_space_component/make_plot_component", "DataCollector agenttype_reporters", "experimental cell_space", "experimental PropertyLayer", "self.rng (numpy Generator)"]},
    "3.0.1": {"band": "3.0", "highlights": ["DEVS bugfixes; Simulator support in SolaraViz"]},
    "3.0.2": {"band": "3.0", "highlights": ["Example-model visualization bugfixes"]},
    "3.0.3": {"band": "3.0", "highlights": ["Allow empty CellCollection; model_parameters init fix"]},
    "3.1.0": {"band": "3.1",
              "highlights": ["mesa.time schedulers REMOVED; Python 3.10 dropped; Agent.create_agents(); Observable/Computable; logging"],
              "breaking": ["mesa.time schedulers removed (ModuleNotFoundError)", "Python 3.10 support dropped"],
              "additions": ["Agent.create_agents()", "Observable/Computable", "n-dimensional property layers"]},
    "3.1.1": {"band": "3.1", "highlights": ["Interactive play-interval slider for visualization"]},
    "3.1.2": {"band": "3.1", "highlights": ["Bugfixes"]},
    "3.1.3": {"band": "3.1",
              "highlights": ["Experimental n-dimensional ContinuousSpace rewrite; seed/rng now seed self.random AND self.rng consistently"],
              "additions": ["experimental mesa.experimental.continuous_space", "draw_voronoi reimplementation"]},
    "3.1.4": {"band": "3.1", "highlights": ["Bugfixes"]},
    "3.1.5": {"band": "3.1", "highlights": ["Last 3.1.x"]},
    "3.2.0": {"band": "3.2",
              "highlights": ["Cell space stabilized as mesa.discrete_space; PropertyLayer stabilized; meta-agents; SolaraViz command console/dark mode/async updates"],
              "breaking": ["experimental cell_space alias still present but superseded by mesa.discrete_space"],
              "additions": ["mesa.discrete_space (stable)", "PropertyLayer (stable)", "meta-agents"]},
    "3.3.0": {"band": "3.3",
              "highlights": ["New visualization API: SpaceRenderer, AgentPortrayalStyle, PropertyLayerStyle; full Altair+Matplotlib; multipage dashboards (backwards compatible)"],
              "additions": ["SpaceRenderer", "AgentPortrayalStyle", "PropertyLayerStyle", "make_plot_component(page=)", "Altair tooltips"]},
    "3.3.1": {"band": "3.3", "highlights": ["PropertyLayer viz bugfixes (HexGrid, Altair/Matplotlib); AgentPortrayalStyle migration docs"]},
    "3.4.0": {"band": "3.4",
              "highlights": ["Universal model.time clock; batch_run(rng=) replaces iterations; Python 3.12+ required; org renamed projectmesa→mesa; experimental cell_space module deleted"],
              "breaking": ["Python 3.11 dropped (3.12+ required)", "mesa.experimental.cell_space deleted (use mesa.discrete_space)", "org/URL rename to github.com/mesa"],
              "deprecations": ["batch_run(iterations=) → rng=", "simulator.time → model.time"],
              "additions": ["model.time universal clock", "batch_run(rng=)"]},
    "3.4.1": {"band": "3.4",
              "highlights": ["Many batch_run/DataCollector fixes (agenttype_reporters in batch_run); PropertyLayer NumPy interface; mesa.space marked maintenance-only; generic Agent/AgentSet/Model types"],
              "additions": ["agenttype_reporters support inside batch_run"]},
    "3.4.2": {"band": "3.4", "highlights": ["Critical memory-leak fix (Agent._ids → Model.register_agent())"]},
    "3.5.0": {"band": "3.5",
              "highlights": ["Public event scheduling on Model (run_for/run_until/schedule_event/schedule_recurring); event system stabilized as new mesa.time; deprecates seed=, Simulator classes, AgentSet indexing, portrayal dicts"],
              "deprecations": ["seed= model param (→ rng=)", "AgentSet indexing/slicing (→ to_list())", "portrayal dicts (→ AgentPortrayalStyle/PropertyLayerStyle)", "Simulator classes (→ model.run_for/schedule_event)", "make_space_component (→ SpaceRenderer)"],
              "additions": ["model.run_for/run_until/schedule_event/schedule_recurring", "new mesa.time event module (Schedule/Event/EventGenerator)", "Agent.from_dataframe", "AgentSet.to_list()", "DataRecorder"]},
    "3.5.1": {"band": "3.5", "highlights": ["Current stable. Backported 4.0 fixes/perf; EventGenerator.pause()/resume(), next_scheduled_time, EventList.compact()"]},
    "4.0.0a0": {"band": "4.0.0a0",
                "highlights": ["ALPHA (breaking). Removes seed=, model.steps, batch_run, mesa.space + agent.pos, PropertyLayer class, Simulator classes; experimental Action system"],
                "breaking": ["mesa.space + agent.pos removed", "model.steps removed (use model.time)", "batch_run removed (→ Scenario)", "seed= removed", "PropertyLayer class removed (→ NumPy arrays)", "Simulator classes removed"],
                "additions": ["experimental Action system"]},
}


def band_for(version):
    """Coarse band from a version string, for versions with no curated band."""
    t = parse_version(version)
    if t >= parse_version("4.0.0a0"):
        return "4.0.0a0"
    if t >= parse_version("3.0.0"):
        return f"{t[0]}.{t[1]}"
    if t >= parse_version("2.1"):
        return "2.1-2.4"
    if t >= parse_version("1.0.0"):
        return "1.x"
    return "0.x"


def python_pin_for(band, requires_python):
    """Curated Python to feed `uv run --python`. Not the floor: a build-reality pin."""
    if band in ("3.4", "3.5", "4.0.0a0"):
        return "3.12"
    if band in ("3.0", "3.1", "3.2", "3.3"):
        return "3.12"
    if band == "2.1-2.4":
        return "3.11"          # old numpy/pandas wheels exist for 3.11 on arm64
    if band == "1.x":
        return "3.10"
    return "3.9"


def install_for(version, band):
    """Band-conditional install string. Extras exist only since 3.0.0."""
    if parse_version(version) >= parse_version("3.0.0"):
        return f'mesa[rec]=={version}'
    return f'mesa=={version}'


def load_pypi(args):
    if args.pypi_json:
        return json.loads(Path(args.pypi_json).read_text())
    with urllib.request.urlopen(PYPI_URL, timeout=30) as r:  # noqa: S310
        return json.loads(r.read().decode())


def mechanical(version, files):
    """Mechanical fields for one release from its PyPI file list."""
    rec = {"version": version, "on_pypi": True}
    if not files:
        rec.update({"date": None, "requires_python": None, "prerelease": False,
                    "yanked": False, "installable": False,
                    "note": "Release exists on PyPI but has NO files — cannot be a target."})
        return rec
    f0 = files[0]
    rec["date"] = (f0.get("upload_time_iso_8601") or "")[:10] or None
    rec["requires_python"] = f0.get("requires_python") or None
    rec["yanked"] = bool(any(x.get("yanked") for x in files))
    rec["installable"] = True
    # PEP 440 pre-release detection via our parser tail.
    t = parse_version(version)
    rec["prerelease"] = t[-2] < 9
    return rec


CURATED_KEYS = ("python_pin", "install", "band", "highlights", "breaking",
                "deprecations", "additions", "note")


def merge(version, mech, existing_by_ver):
    """Mechanical fields + curated (existing catalog wins, else CURATION seed, else derived)."""
    rec = dict(mech)
    prev = existing_by_ver.get(version, {})
    seed = CURATION.get(version, {})
    band = prev.get("band") or seed.get("band") or band_for(version)
    rec["band"] = band
    rec["python_pin"] = prev.get("python_pin") or seed.get("python_pin") or python_pin_for(band, mech.get("requires_python"))
    if mech.get("installable", True):
        rec["install"] = prev.get("install") or seed.get("install") or install_for(version, band)
    else:
        rec["install"] = None
    for key in ("highlights", "breaking", "deprecations", "additions"):
        val = prev.get(key)
        if val is None:
            val = seed.get(key)
        if val is not None:
            rec[key] = val
    note = prev.get("note") or seed.get("note") or mech.get("note")
    if note:
        rec["note"] = note
    return rec, bool(seed) or bool(prev.get("band"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pypi-json", help="offline PyPI JSON file (else fetch live)")
    ap.add_argument("--out", default=str(CATALOG))
    args = ap.parse_args()

    data = load_pypi(args)
    releases = data["releases"]

    existing = {}
    out_path = Path(args.out)
    if out_path.exists():
        try:
            prev = json.loads(out_path.read_text())
            existing = {r["version"]: r for r in prev.get("releases", [])}
        except Exception:  # noqa: BLE001
            existing = {}

    records, needs = [], []
    for version in sorted(releases, key=parse_version):
        mech = mechanical(version, releases[version])
        rec, curated = merge(version, mech, existing)
        records.append(rec)
        if not curated and parse_version(version) >= parse_version("2.1"):
            needs.append(version)

    # Ghosts (not on PyPI): keep if not already represented.
    have = {r["version"] for r in records}
    for g in GHOSTS:
        if g["version"] not in have:
            records.append(dict(g))
    records.sort(key=lambda r: parse_version(r["version"]))

    stable = [r["version"] for r in records
              if r.get("on_pypi") and not r.get("prerelease") and r.get("installable", True)]
    prereleases = [r["version"] for r in records if r.get("prerelease")]

    catalog = {
        "$comment": "Complete Mesa release catalog. Mechanical fields (date, "
                    "requires_python, prerelease, yanked, on_pypi, installable) are "
                    "regenerated by scripts/update_catalog.py from PyPI; curated fields "
                    "(python_pin, install, band, highlights, breaking, deprecations, "
                    "additions) are hand-maintained and preserved across regens. "
                    "Narrative deep-dive: version-history.md. Full curation 2.1+; coarse below.",
        "schema": 1,
        "latest_stable": stable[-1] if stable else None,
        "latest_prerelease": prereleases[-1] if prereleases else None,
        "count": len(records),
        "releases": records,
    }
    out_path.write_text(json.dumps(catalog, indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {out_path} — {len(records)} releases "
          f"(latest stable {catalog['latest_stable']}, "
          f"latest pre {catalog['latest_prerelease']}).")
    if needs:
        print(f"NEEDS CURATION ({len(needs)}): {', '.join(needs)}")


if __name__ == "__main__":
    main()
