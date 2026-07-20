#!/usr/bin/env python3
"""Scan notebooks / .py files for Mesa APIs, computing status at a TARGET version.

For every registry pattern hit, the status is computed at --target from the
entry's lifecycle ({introduced, deprecated, superseded, removed}):

    not-yet-introduced : API is newer than the target — remove it or rewrite to
                         the target-era idiom (this is how migrations avoid
                         overshooting, and the work list for downgrades)
    removed            : errors at the target — must fix
    deprecated         : warns at the target — must fix (unfinished migration)
    legacy             : silently superseded, slated for removal — migrate
    install            : pip-install line — repin to the target
    stale-term         : prose marker — verify the text teaches target behavior
    judge              : ambiguous — examine each hit

Every hit is fixed or explicitly judged a false positive — never skipped.

Usage:
    python3 scan_notebook.py NB.ipynb [more...] --target X.Y.Z [--json]
                                              [--catalog PATH | --no-catalog]
                                              [--show-current]

Exit codes: 0 = no findings; 1 = findings to process; 2 = bad input/target.
Stdlib only — runs on any Python 3.9+, no installs needed.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesa_versions import (  # noqa: E402
    parse_version, status_at, in_applicable_range, pick_by_target, validate_lifecycle,
)

HERE = Path(__file__).resolve().parent
DEFAULT_REGISTRY = HERE.parent / "references" / "api-registry.json"
DEFAULT_CATALOG = HERE.parent / "references" / "version-catalog.json"

SUPPRESS = object()  # sentinel: entry matched but is not a finding at this target


def iter_cells(path: Path):
    """Yield (cell_index, cell_type, source_text). A .py file is one code cell."""
    if path.suffix == ".ipynb":
        nb = json.loads(path.read_text(encoding="utf-8"))
        for i, cell in enumerate(nb.get("cells", [])):
            src = cell.get("source", "")
            if isinstance(src, list):
                src = "".join(src)
            yield i, cell.get("cell_type", "code"), src
    else:
        yield 0, "code", path.read_text(encoding="utf-8")


def install_pin_ok(line, target, target_str):
    """True when a pip-install line already pins the exact target with the
    band-correct extras — the finding is resolved, not re-flagged."""
    esc = re.escape(target_str)
    if target >= parse_version("3.0.0"):
        # need an extras bracket containing rec or all, and the exact pin
        return re.search(rf"(?i)\bmesa\[[^\]]*\b(rec|all)\b[^\]]*\]\s*==\s*{esc}\b", line) is not None
    # pre-3.0: plain pin, no extras bracket
    return (re.search(rf"(?i)\bmesa\s*==\s*{esc}\b", line) is not None
            and re.search(r"(?i)\bmesa\[", line) is None)


def effective(entry, target):
    """Return (status, replacement, note) for an entry at target, or SUPPRESS.

    SUPPRESS means the pattern matched but is not a finding at this target
    (e.g. a lifecycle-current API with no judge flag) — still recorded as era
    evidence, never shown as work unless --show-current.
    """
    if not in_applicable_range(entry, target):
        return SUPPRESS
    kind = entry.get("kind", "api")
    band = pick_by_target(entry.get("by_target"), target)
    replacement = (band or {}).get("replacement") or entry.get("replacement", "")
    note = (band or {}).get("note") or entry.get("note", "")

    if kind == "install":
        status = "install"
    else:
        status = (band or {}).get("status") or status_at(entry, target)
        if kind == "prose":
            if status == "current":
                status = SUPPRESS if not entry.get("judge") else "judge"
            elif status != "not-yet-introduced":
                status = "stale-term"
        elif status == "current":
            status = "judge" if entry.get("judge") else SUPPRESS
    if status is SUPPRESS:
        return SUPPRESS
    return status, replacement, note


KEEP_RULE_APIS = {"old-space-imports", "old-grid-methods", "agent-pos"}
LEGACY_GRID_RX = re.compile(
    r"\b(MultiGrid|SingleGrid|HexSingleGrid|HexMultiGrid|NetworkGrid)\b")


def _call_spans(text, func="batch_run"):
    """Char spans (start_of_name, index_of_matching_close_paren) of each
    balanced `func(...)` call in text — so a kwarg can be scoped to the call it
    belongs to even when the call spans several lines."""
    spans = []
    for m in re.finditer(r"\b" + re.escape(func) + r"\(", text):
        depth, j, n = 0, m.end() - 1, len(text)
        while j < n:
            c = text[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    spans.append((m.start(), j))
                    break
            j += 1
        else:
            spans.append((m.start(), n))  # unbalanced — take the rest
    return spans


def _line_start_offsets(src):
    """offs[L-1] = char offset of the first char of 1-indexed line L."""
    offs = [0]
    for line in src.split("\n"):
        offs.append(offs[-1] + len(line) + 1)
    return offs


def apply_batchrun_context(path: Path, findings, target, entries):
    """Scope batch_run kwargs to the actual `batch_run(...)` call, and catch a
    multi-line `batch_run(rng=...)`.

    Two concerns, both because `batch_run(...)` calls routinely span lines while
    the pattern scan is per-line:

    1. `iterations=` is a batch_run kwarg, but *any* function takes one
       (networkx `spring_layout(iterations=50)`, sklearn, ...). A
       batch-run-iterations hit that is NOT inside a `batch_run(...)` call is
       downgraded to `judge` (belongs to another function) — precisely, per
       call, so a file that uses batch_run *and* spring_layout no longer
       false-flags the networkx kwarg (nor misses a real batch_run one).

    2. `batch-run-rng` (introduced 3.4) is caught per-line only when `batch_run(`
       and `rng=` share a line. When the call spans lines, a downgrade target
       (<3.4) would silently miss a real not-yet-introduced anachronism that
       *crashes* there (3.3 batch_run has no rng=). Emit it, scoped to the call
       so a model-kwarg `rng=` elsewhere is never conflated.
    """
    try:
        cells = [(idx, src) for idx, ctype, src in iter_cells(path) if ctype == "code"]
    except Exception:  # noqa: BLE001
        return findings
    spans_by_cell = {idx: _call_spans(src) for idx, src in cells}
    src_by_cell = {idx: src for idx, src in cells}

    def line_in_batchrun(idx, line_no):
        src = src_by_cell.get(idx)
        if src is None:
            return False
        offs = _line_start_offsets(src)
        if line_no < 1 or line_no >= len(offs):
            return False
        lstart, lend = offs[line_no - 1], offs[line_no] - 1
        return any(s <= lend and lstart <= e for (s, e) in spans_by_cell.get(idx, []))

    # (1) iterations= not inside any batch_run(...) call -> judge (foreign kwarg)
    note_it = ("this iterations= is not inside a batch_run(...) call — it belongs "
               "to another function (networkx spring_layout etc.); verify and "
               "record as a false positive if so.")
    for f in findings:
        if f["file"] == str(path) and f["api"] == "batch-run-iterations" \
                and f["status"] in ("deprecated", "removed") \
                and not line_in_batchrun(f["cell"], f["line_in_cell"]):
            f["status"] = "judge"
            f["note"] = note_it

    # (2) multi-line batch_run(rng=...) — only actionable when rng= is not yet
    #     current at the target (i.e. a <3.4 downgrade); at >=3.4 effective()
    #     returns SUPPRESS and there is nothing to flag.
    entry = next((e for e in entries if e["id"] == "batch-run-rng"), None)
    if entry is not None:
        eff = effective(entry, target)
        if eff is not SUPPRESS:
            status, replacement, note = eff
            already = {(f["cell"], f["line_in_cell"])
                       for f in findings if f["api"] == "batch-run-rng"}
            for idx, src in cells:
                for (s, e) in spans_by_cell.get(idx, []):
                    rm = re.search(r"\brng\s*=", src[s:e])
                    if not rm:
                        continue
                    line_no = src.count("\n", 0, s + rm.start()) + 1
                    if (idx, line_no) in already:
                        continue
                    already.add((idx, line_no))
                    findings.append({
                        "file": str(path), "cell": idx, "cell_type": "code",
                        "line_in_cell": line_no,
                        "text": src.split("\n")[line_no - 1].strip()[:200],
                        "api": "batch-run-rng", "status": status,
                        "replacement": replacement.replace("{TARGET}", str(target_str_holder[0])),
                        "note": (note + " [multi-line batch_run(...) call]").strip(),
                        "introduced": entry.get("introduced"), "deprecated": entry.get("deprecated"),
                        "superseded": entry.get("superseded"), "removed": entry.get("removed"),
                    })
    return findings


def apply_continuous_keep_rule(path: Path, findings):
    """Policy exception, applied file-wide after scanning.

    When a file keeps legacy mesa.space.ContinuousSpace (the KEEP rule — its
    stable replacement doesn't exist through 3.5.x) and has NO legacy grid
    classes, the ContinuousSpace API surface itself (its import, .pos,
    place_agent/move_agent/get_neighbors) unavoidably matches the legacy
    patterns. Those hits are downgraded to `judge` with the keep-rule note —
    they are the kept space's own API, not unfinished migration. Any legacy
    grid class present disables the downgrade (the hits become ambiguous and
    must be resolved by the migration).
    """
    try:
        text = "".join(src for _, ctype, src in iter_cells(path) if ctype == "code")
    except Exception:  # noqa: BLE001
        return findings
    if "ContinuousSpace" not in text or LEGACY_GRID_RX.search(text):
        return findings
    note = ("KEEP-rule: attributable to kept legacy ContinuousSpace (stable "
            "replacement doesn't exist) — verify the hit belongs to the "
            "continuous space and report it as a pending Mesa-4 item.")
    for f in findings:
        if f["file"] == str(path) and f["api"] in KEEP_RULE_APIS and f["status"] == "legacy":
            f["status"] = "judge"
            f["note"] = note
    return findings


def scan_file(path: Path, entries, target, keep_current):
    findings, evidence = [], []
    for idx, ctype, src in iter_cells(path):
        if ctype == "raw":
            continue
        for line_no, line in enumerate(src.splitlines(), 1):
            for e in entries:
                scope = e.get("applies_to", "both")
                if scope != "both" and scope != ctype:
                    continue
                if not any(rx.search(line) for rx in e["_rx"]):
                    continue
                # Era evidence: any matched API with an introduced stamp bounds
                # the lower era; any with a deprecation/removal bounds the upper.
                evidence.append({"id": e["id"], "cell_type": ctype,
                                 "introduced": e.get("introduced"),
                                 "deprecated": e.get("deprecated"),
                                 "superseded": e.get("superseded"),
                                 "removed": e.get("removed")})
                eff = effective(e, target)
                if eff is SUPPRESS:
                    if not keep_current:
                        continue
                    status, replacement, note = "current", e.get("replacement", ""), e.get("note", "")
                else:
                    status, replacement, note = eff
                    if status == "install" and install_pin_ok(line, target, target_str_holder[0]):
                        # pin already matches the target with band-correct extras —
                        # resolved, not a finding
                        if not keep_current:
                            continue
                        status, note = "current", "install pin already correct for the target"
                findings.append({
                    "file": str(path), "cell": idx, "cell_type": ctype,
                    "line_in_cell": line_no, "text": line.strip()[:200],
                    "api": e["id"], "status": status,
                    "replacement": replacement.replace("{TARGET}", str(target_str_holder[0])),
                    "note": note,
                    "introduced": e.get("introduced"), "deprecated": e.get("deprecated"),
                    "superseded": e.get("superseded"), "removed": e.get("removed"),
                })
    return findings, evidence


def era_bracket(evidence, target):
    """Two-sided era estimate from matched-entry lifecycles (code cells only)."""
    code = [e for e in evidence if e["cell_type"] == "code"]
    lowers = [parse_version(e["introduced"]) for e in code if e["introduced"]]
    lower = max(lowers) if lowers else None
    uppers = []
    for e in code:
        for f in ("deprecated", "superseded", "removed"):
            if e[f]:
                v = parse_version(e[f])
                # only counts as upper evidence if the idiom is already stale at target
                if target >= v:
                    uppers.append(v)
    upper = min(uppers) if uppers else None
    return lower, upper


def fmt(v):
    return ".".join(str(x) for x in v[:3]) if v else None


target_str_holder = [""]  # filled in main() for {TARGET} substitution


def load_catalog(path):
    try:
        cat = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return {r["version"]: r for r in cat.get("releases", [])}


def validate_target(target_str, catalog):
    """Return (ok, message). Hard error on unknown; warn on prerelease/uninstallable."""
    if catalog is None:
        return True, None
    rec = catalog.get(target_str)
    if rec is None:
        # normalize (2.1 vs 2.1.0)
        want = parse_version(target_str)
        for v, r in catalog.items():
            try:
                if parse_version(v) == want:
                    rec = r
                    break
            except ValueError:
                continue
    if rec is None:
        return False, (f"Target {target_str!r} is not a known Mesa release. "
                       f"Nearest known: {', '.join(_nearest(catalog, target_str))}. "
                       f"(Run scripts/update_catalog.py if Mesa released it recently.)")
    if rec.get("on_pypi") is False:
        return False, (f"Target {target_str!r} is in the changelog but was never "
                       f"uploaded to PyPI — cannot install. {rec.get('note','')}")
    if rec.get("installable") is False:
        return False, (f"Target {target_str!r} exists on PyPI but has NO files — "
                       f"cannot install. {rec.get('note','')}")
    if rec.get("prerelease"):
        return True, (f"NOTE: {target_str} is a PRE-RELEASE (breaking, unstable). "
                      f"Proceed only if the user explicitly asked for it.")
    if rec.get("yanked"):
        return True, f"NOTE: {target_str} was YANKED from PyPI — confirm with the user."
    return True, None


def _nearest(catalog, target_str, k=5):
    """The k known versions closest to target in version order (neighbors below/above)."""
    try:
        t = parse_version(target_str)
    except ValueError:
        return list(catalog)[:k]
    known = []
    for v in catalog:
        try:
            known.append((parse_version(v), v))
        except ValueError:
            continue
    known.sort()
    below = [v for pv, v in known if pv < t][-k:]
    above = [v for pv, v in known if pv >= t][:k]
    both = below + above
    both.sort(key=parse_version)
    return both[:k] if len(both) <= k else below[-2:] + above[:k - 2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--target", required=True,
                    help="Mesa target version, e.g. 3.5.1 or 3.3.0 (required; from SKILL.md Step 1)")
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    ap.add_argument("--no-catalog", action="store_true",
                    help="skip catalog validation of the target")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--show-current", action="store_true",
                    help="also list matched-but-current idioms (era evidence)")
    args = ap.parse_args()

    try:
        target = parse_version(args.target)
    except ValueError as exc:
        print(f"Bad --target: {exc}", file=sys.stderr)
        return 2
    target_str_holder[0] = args.target

    catalog = None if args.no_catalog else load_catalog(args.catalog)
    ok, msg = validate_target(args.target, catalog)
    if not ok:
        print(msg, file=sys.stderr)
        return 2
    if msg and not args.json:
        print(msg + "\n", file=sys.stderr)

    try:
        registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"Could not load registry: {exc}", file=sys.stderr)
        return 2
    if registry.get("schema") != 2:
        print("Registry is not schema v2 — this scanner needs the lifecycle registry.",
              file=sys.stderr)
        return 2
    entries = registry["entries"]
    for e in entries:
        validate_lifecycle(e)  # hard-fail on prose in a version field
        e["_rx"] = [re.compile(p) for p in e["patterns"]]

    all_findings, all_evidence = [], []
    for f in args.files:
        path = Path(f)
        if not path.exists():
            print(f"No such file: {path}", file=sys.stderr)
            return 2
        fnd, ev = scan_file(path, entries, target, args.show_current)
        fnd = apply_continuous_keep_rule(path, fnd)
        fnd = apply_batchrun_context(path, fnd, target, entries)
        all_findings.extend(fnd)
        all_evidence.extend(ev)

    # ACTIONABLE findings must be fixed and must reach zero ("re-scan until
    # zero"). JUDGE findings are surfaced for a human decision (fix or record as
    # a false positive) — a correct discrete_space migration always carries some
    # (e.g. cell-space-classes on every CellAgent), so they must NOT block the
    # zero gate or the exit code. current rows appear only under --show-current.
    ACTIONABLE = {"removed", "deprecated", "legacy",
                  "not-yet-introduced", "install", "stale-term"}
    actionable = [f for f in all_findings if f["status"] in ACTIONABLE]
    judge = [f for f in all_findings if f["status"] == "judge"]
    work = actionable + judge  # everything needing attention (display order)
    lower, upper = era_bracket(all_evidence, target)

    display = all_findings if args.show_current else work
    by_status, by_api = {}, {}
    for f in display:
        by_status[f["status"]] = by_status.get(f["status"], 0) + 1
        by_api[f["api"]] = by_api.get(f["api"], 0) + 1

    if args.json:
        print(json.dumps({
            "target": args.target,
            "era_lower": fmt(lower), "era_upper": fmt(upper),
            "era_conflict": bool(lower and upper and lower >= upper),
            "count": len(actionable),          # the number that must reach zero
            "actionable_count": len(actionable),
            "judge_count": len(judge),
            "summary": {"by_status": by_status, "by_api": by_api},
            "findings": display,
        }, indent=1))
    else:
        print(f"Target: mesa {args.target} — statuses computed at this version.\n")
        for f in actionable + judge + (
                [g for g in all_findings if g["status"] == "current"] if args.show_current else []):
            loc = f"{Path(f['file']).name} cell {f['cell']} ({f['cell_type']}) line {f['line_in_cell']}"
            print(f"[{f['status'].upper():18s}] {loc}")
            print(f"    {f['text']}")
            print(f"    api: {f['api']}  →  {f['replacement']}")
            if f["note"]:
                print(f"    note: {f['note']}")
        print(f"\n{len(actionable)} actionable finding(s)"
              + (" — FIX all to reach zero" if actionable else " (zero — clean at target)")
              + f"; {len(judge)} judge item(s) to confirm, at target {args.target}.")
        if lower or upper:
            lo = fmt(lower) or "?"
            hi = fmt(upper) or "?"
            if lower and upper and lower >= upper:
                print(f"Era: MIXED — evidence ≥ {lo} conflicts with idioms stale since {hi} "
                      f"(half-migrated notebook; reconcile both sides).")
            else:
                direction = ""
                if lower and lower > target:
                    direction = " — DOWNGRADE (target is older than the code's era; " \
                                "not-yet-introduced findings are the work list)"
                print(f"Era: written for Mesa ≥ {lo}" + (f", < {hi}" if upper else "") +
                      f" — migrating to {args.target}{direction}.")
    return 1 if actionable else 0


if __name__ == "__main__":
    sys.exit(main())
