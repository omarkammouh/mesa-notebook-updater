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

Exit codes: 0 = zero ACTIONABLE findings (judge items may remain — they are
surfaced for a human decision and never block); 1 = actionable findings to fix;
2 = bad input/target.
Stdlib only — runs on any Python 3.9+, no installs needed.
"""
import argparse
import ast
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
    """True when a pip-install line already pins EXACTLY the target version
    (compared via parse_version, so `==3.5` never passes for 3.5.1 and
    `==v3.5.1`/`==03.5.1` never get prescribed) with the band-correct extras."""
    m = re.search(r"(?i)\bmesa\s*(\[[^\]]*\])?\s*==\s*([0-9][0-9a-zA-Z.]*)", line)
    if not m:
        return False
    extras, pinned = m.group(1) or "", m.group(2)
    try:
        if parse_version(pinned) != target:
            return False
    except ValueError:
        return False
    if target >= parse_version("3.0.0"):
        return re.search(r"(?i)\b(rec|all)\b", extras) is not None
    return extras == ""


def _judges_when_current(entry):
    """True when a judge entry should still SURFACE at a target where its API is
    simply current.

    `judge: true` carries two independent meanings; they are separated by
    `judge_when`:

      "always" (default) — the entry adds a check a human must run even on
          correct target-era code: the ContinuousSpace keep rule, the
          `random=self.random` / base-class-by-mobility checks on cell-space
          classes, the batch_run checklist. Worth the line.
      "stale"  — the flag exists ONLY so the entry cannot hard-block the zero
          gate when its pattern is ambiguous (pandas `.to_list()`, numpy
          `.rng`, a `re` match's `.pos`). At a target where the API is current
          there is nothing to decide, so announcing it is pure noise — on a
          finished migration these were ~46% of all judge items, and a judge
          list nobody reads is worse than a shorter one someone does.
    """
    return entry.get("judge") and entry.get("judge_when", "always") != "stale"


def effective(entry, target):
    """Return (status, replacement, note) for an entry at target, or SUPPRESS.

    SUPPRESS means the pattern matched but is not a finding at this target
    (e.g. a lifecycle-current API with no judge flag) — still recorded as era
    evidence, never shown as work unless --show-current.

    An explicit `status` in a matched by_target band is curated intent and is
    honored verbatim — in particular `"judge"` surfaces the hit without blocking
    the zero gate (for prose whose staleness needs a human to confirm the hit is
    Mesa's kwarg and not another library's), and `"current"` suppresses.
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
        band_status = (band or {}).get("status")
        if band_status is not None:
            status = band_status
            if status == "current":
                status = "judge" if _judges_when_current(entry) else SUPPRESS
        else:
            status = status_at(entry, target)
            if kind == "prose":
                if status == "current":
                    status = "judge" if _judges_when_current(entry) else SUPPRESS
                elif status != "not-yet-introduced":
                    status = "stale-term"
            elif status == "current":
                status = "judge" if _judges_when_current(entry) else SUPPRESS
            # judge:true means "this pattern cannot self-certify" (pandas
            # .to_list(), numpy .rng, re-match .pos, ...). That ambiguity does
            # not vanish when the lifecycle says stale — so an ambiguous
            # pattern NEVER hard-blocks the zero gate. The computed status is
            # kept in the note; the human judges the hit either way.
            if status is not SUPPRESS and status != "judge" and entry.get("judge"):
                note = (f"(computed: {status} at the target — judge pattern, "
                        f"never blocks zero) " + note).strip()
                status = "judge"
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


def _blank_comments(src):
    """Replace #-comment text with spaces, length-preserving, so a flattened
    rescan cannot match across comment prose (per-line scans still see it)."""
    return re.sub(r"#[^\n]*", lambda m: " " * len(m.group()), src)


def apply_multiline_entries(path: Path, findings, target, entries):
    """Rerun registry entries flagged `multiline:true` on a newline-flattened
    copy of each code cell (comments blanked, offsets preserved).

    Per-line scanning misses a kwarg whose call spans lines — e.g.
        super().__init__(
            seed=seed,
        )
    never puts `super().__init__(` and `seed` on one line, so the code-shaped
    pattern `super\\(\\)...__init__\\([^)]*\\bseed\\b` can't fire and a
    deprecated (3.5+) or not-yet-introduced kwarg slips through. Flattening
    newlines to spaces (1:1, so char offsets and line attribution survive)
    lets `[^)]*` cross the former line breaks while `)` still bounds the call.
    Findings are attributed to the line where the match starts (the call head)
    and deduped against per-line findings on (api, cell, line)."""
    ml = [e for e in entries if e.get("multiline")]
    if not ml:
        return findings
    try:
        cells = [(idx, src) for idx, ctype, src in iter_cells(path) if ctype == "code"]
    except Exception:  # noqa: BLE001
        return findings
    seen = {(f["api"], f["cell"], f["line_in_cell"])
            for f in findings if f["file"] == str(path)}
    for idx, src in cells:
        flat = _blank_comments(src).replace("\n", " ")
        lines = src.split("\n")
        for e in ml:
            eff = effective(e, target)
            if eff is SUPPRESS:
                continue
            status, replacement, note = eff
            for rx in e["_rx"]:
                for m in rx.finditer(flat):
                    line_no = src.count("\n", 0, m.start()) + 1
                    key = (e["id"], idx, line_no)
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append({
                        "file": str(path), "cell": idx, "cell_type": "code",
                        "line_in_cell": line_no,
                        "text": lines[line_no - 1].strip()[:200],
                        "api": e["id"], "status": status,
                        "replacement": replacement.replace("{TARGET}", str(target_str_holder[0])),
                        "note": (note + " [multi-line call]").strip(),
                        "introduced": e.get("introduced"), "deprecated": e.get("deprecated"),
                        "superseded": e.get("superseded"), "removed": e.get("removed"),
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
    # The space must actually be USED (imported or constructed) — a mere
    # mention in a comment/string must not neutralize legacy findings, so
    # comments are blanked before the check.
    code = _blank_comments(text)
    constructed = re.search(
        r"ContinuousSpace\s*\(|mesa\.space\.ContinuousSpace"
        r"|from\s+mesa\.space\s+import[^\n]*ContinuousSpace", code)
    if not constructed or LEGACY_GRID_RX.search(code):
        return findings
    note = ("KEEP-rule: attributable to kept legacy ContinuousSpace (stable "
            "replacement doesn't exist) — verify the hit belongs to the "
            "continuous space and report it as a pending Mesa-4 item.")
    for f in findings:
        if f["file"] == str(path) and f["api"] in KEEP_RULE_APIS and f["status"] == "legacy":
            f["status"] = "judge"
            f["note"] = note
    return findings


DISCRETE_SPACE_RX = re.compile(r"\bmesa\s*\.\s*discrete_space\b")
PLAIN_AGENT_DECL_RX = re.compile(r"^[ \t]*class\s+(\w+)\s*\(\s*(?:mesa\s*\.\s*)?Agent\s*\)\s*:")


def _class_body(lines, decl_i):
    """Source lines of the class body that starts at lines[decl_i] (indent-based)."""
    decl_indent = len(lines[decl_i]) - len(lines[decl_i].lstrip())
    body = []
    for ln in lines[decl_i + 1:]:
        if ln.strip() == "":
            body.append(ln)
            continue
        if len(ln) - len(ln.lstrip()) <= decl_indent:
            break
        body.append(ln)
    return "\n".join(body)


def apply_cell_space_base_rule(path: Path, findings, target):
    """File-wide rule: plain `class X(Agent)` in a file that uses
    mesa.discrete_space (stable 3.2+).

    A plain mesa.Agent placed on a discrete_space grid is SILENTLY broken:
    `self.cell = grid[node]` constructs without error but the agent registers
    on NO cell — cell.agents / all_cells.agents stay empty and every
    neighbor-based mechanic quietly returns nothing (verified on 3.5.1). A
    green run does not expose this.

    Tier A — the class body references self.cell: it clearly lives on the cell
    space -> actionable (status `legacy`). The base must be CellAgent (moves),
    FixedAgent (never moves) or Grid2DMovingAgent (compass moves).
    Tier B — plain Agent in a discrete_space file without self.cell in its
    body -> `judge`: confirm the class is genuinely non-spatial (a spaceless
    agent correctly stays mesa.Agent), or fix its base if instances are placed
    on the grid elsewhere.
    """
    if target < parse_version("3.2.0"):
        return findings
    try:
        cells = [(idx, src) for idx, ctype, src in iter_cells(path) if ctype == "code"]
    except Exception:  # noqa: BLE001
        return findings
    if not any(DISCRETE_SPACE_RX.search(src) for _, src in cells):
        return findings
    repl = ("mesa.discrete_space base classes: CellAgent (movable), FixedAgent "
            "(immobile patch/site/node), Grid2DMovingAgent (compass moves). "
            "Non-spatial agents stay mesa.Agent.")
    for idx, src in cells:
        lines = src.split("\n")
        for i, ln in enumerate(lines):
            m = PLAIN_AGENT_DECL_RX.match(ln)
            if not m:
                continue
            uses_cell = re.search(r"\bself\.cell\b", _class_body(lines, i))
            findings.append({
                "file": str(path), "cell": idx, "cell_type": "code",
                "line_in_cell": i + 1, "text": ln.strip()[:200],
                "api": "cell-space-base-class",
                "status": "legacy" if uses_cell else "judge",
                "replacement": repl,
                "note": ("class body uses self.cell — this agent lives on the "
                         "cell space; a plain mesa.Agent registers on NO cell "
                         "(silent empty cell.agents, verified on 3.5.1). Change "
                         "the base class."
                         if uses_cell else
                         "file uses mesa.discrete_space — confirm this plain "
                         "mesa.Agent is genuinely non-spatial (then it is "
                         "correct as-is); if instances are placed on the grid "
                         "(agent.cell = ...), the base MUST be CellAgent/"
                         "FixedAgent — a plain Agent registers on NO cell "
                         "(silent wrong results, not a crash)."),
                "introduced": "3.2.0", "deprecated": None,
                "superseded": None, "removed": None,
            })
    return findings


def scan_file(path: Path, entries, target, keep_current):
    findings, evidence = [], []
    for idx, ctype, src in iter_cells(path):
        # raw cells hold rendered prose (LaTeX/reST passthrough) — scan them
        # with the markdown-scope patterns; a stale API name there is as real
        # as one in a markdown cell.
        scan_scope = "markdown" if ctype == "raw" else ctype
        for line_no, line in enumerate(src.splitlines(), 1):
            for e in entries:
                scope = e.get("applies_to", "both")
                if scope != "both" and scope != scan_scope:
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


# Also covers the multi-type form: `agents_by_type[T].shuffle_do("step")` is the
# standard activation idiom for a multi-species model, and below 3.0 it drives
# the clock exactly as little as `agents.shuffle_do` does.
AGENTSET_CLOCK_RX = re.compile(
    r"\.agents(?:_by_type\s*\[[^\]\n]*\])?\s*\.\s*(shuffle_do|do)\s*\(")
SCHEDULER_NAMES = (r"BaseScheduler|RandomActivation|SimultaneousActivation"
                   r"|StagedActivation|RandomActivationByType"
                   r"|RandomActivationByBreed")
# A scheduler must be CONSTRUCTED (a call, not a bare mention) to count at all.
SCHEDULER_CTOR_RX = re.compile(rf"\b(?:{SCHEDULER_NAMES})\s*\(")
# ...and the attribute it is bound to is what .step()/.add() are then sought on.
SCHEDULER_ASSIGN_RX = re.compile(
    rf"(?:self\s*\.\s*)?(\w+)\s*=\s*(?:\w+\s*\.\s*)*(?:{SCHEDULER_NAMES})\s*\(")

_STRING_RX = re.compile(
    r"[bBrRuUfF]{0,2}('''|\"\"\")(?:\\.|(?!\1)[^\\])*?\1"
    r"|[bBrRuUfF]{0,2}\"(?:\\.|[^\"\\\n])*\""
    r"|[bBrRuUfF]{0,2}'(?:\\.|[^'\\\n])*'")


def _blank_strings(src):
    """Blank string literals length-preservingly, keeping newlines.

    Deliberately NOT folded into `_blank_comments`: the flattened rescans and
    the prose checks MUST still see inside docstrings, because a dead API name
    in a docstring is a real finding. Only the sub-3.0 clock rule needs this —
    there, a docstring that merely *mentions* `RandomActivation` (a notebook
    narrating its own migration history) would otherwise satisfy the scheduler
    check and silence a model that then hangs forever.
    """
    return _STRING_RX.sub(
        lambda m: "".join("\n" if c == "\n" else " " for c in m.group()), src)


def _scheduler_state(code):
    """(constructed, driven, populated) for scheduler use in `code`.

    `code` must already have comments and string literals blanked.
    driven   == some scheduler's `.step()` is called — that is what actually
                advances `model._steps` below 3.0, and its absence is the hang.
    populated== some scheduler's `.add()` is called — that is what actually
                gets agents activated; without it the model runs but does
                nothing.
    """
    constructed = bool(SCHEDULER_CTOR_RX.search(code))
    names = {m.group(1) for m in SCHEDULER_ASSIGN_RX.finditer(code)}
    names.add("schedule")  # the conventional attribute name, always considered
    driven = populated = False
    for n in names:
        if re.search(rf"\b{re.escape(n)}\s*\.\s*step\s*\(", code):
            driven = True
        if re.search(rf"\b{re.escape(n)}\s*\.\s*add\s*\(", code):
            populated = True
    return constructed, driven, populated


def _locate(cells, offset):
    """(cell_index, line_in_cell) for a character offset into the joined code."""
    run = 0
    for idx, src in cells:
        if offset < run + len(src):
            return idx, src[:offset - run].count("\n") + 1
        run += len(src)
    return (cells[-1][0], 1) if cells else (0, 1)


def apply_pre3_clock_rule(path: Path, findings, target):
    """File-wide rule for DOWNGRADES below 3.0: AgentSet activation does not
    advance the clock there.

    The AgentSet surface (`model.agents`, `do`/`shuffle_do`/`select`/...) exists
    from 2.4, so AgentSet activation *looks* portable down to 2.4 — it is not:

      * `model.steps` does not exist below 3.0 (2.x has only the private
        `_steps`) — the `model-steps-attr` entry covers that hit;
      * `batch_run` loops `while model.running and model._steps <= max_steps`,
        and `_steps` is advanced only by a scheduler's `step()`.

    So a model that keeps `agents.shuffle_do("step")` with no scheduler scans
    clean at a 2.x target and then **hangs forever** in every `batch_run` cell —
    no exception, 100% CPU (verified on 2.4.0). Nothing regex-per-line can see
    an *absent* scheduler, hence this file-wide check.
    """
    if target >= parse_version("3.0.0"):
        return findings
    try:
        cells = [(i, src) for i, ctype, src in iter_cells(path) if ctype == "code"]
    except Exception:  # noqa: BLE001
        return findings
    code = _blank_strings(_blank_comments("".join(src for _, src in cells)))
    constructed, driven, populated = _scheduler_state(code)
    has_batch = "batch_run(" in code

    if constructed and driven and not populated:
        # The clock advances, so this does not hang — but no agent was ever
        # handed to the scheduler, so every step activates nothing. Silent.
        m = SCHEDULER_CTOR_RX.search(code)
        idx, line_no = _locate(cells, m.start()) if m else (0, 1)
        findings.append({
            "file": str(path), "cell": idx, "cell_type": "code",
            "line_in_cell": line_no, "text": m.group(0) if m else "scheduler",
            "api": "pre3-scheduler-unpopulated", "status": "removed",
            "replacement": ("Call self.schedule.add(agent) at every agent-construction "
                            "site. Below 3.0 agents are NOT auto-registered — "
                            "`schedule.step()` iterates only what `.add()` put in it."),
            "note": ("A scheduler is constructed and stepped, but nothing is ever added "
                     "to it. The model runs and the clock advances, so this is silent: "
                     "every step activates zero agents and the run produces flat, "
                     "empty results rather than an error."),
            "introduced": "3.0.0", "deprecated": None, "superseded": None,
            "removed": None,
        })
        return findings

    if driven:
        return findings  # a scheduler actually drives the clock — nothing to flag

    hit = None
    for idx, src in cells:
        m = AGENTSET_CLOCK_RX.search(_blank_strings(_blank_comments(src)))
        if m:
            hit = (idx, src[:m.start()].count("\n") + 1, m.group(0))
            break
    if hit is None:
        if not constructed:
            return findings
        # A scheduler exists but is never stepped: the clock is not driven by
        # anything, which is the same hang by a different route.
        m = SCHEDULER_CTOR_RX.search(code)
        hit = (*_locate(cells, m.start()), m.group(0))
    idx, line_no, text = hit
    findings.append({
        "file": str(path), "cell": idx, "cell_type": "code",
        "line_in_cell": line_no, "text": text,
        "api": "pre3-agentset-clock", "status": "not-yet-introduced",
        "replacement": ("Below 3.0 the AgentSet does not drive the clock. Reintroduce a "
                        "scheduler: self.schedule = RandomActivation(self) (from mesa.time), "
                        "self.schedule.add(agent) at every construction site, and "
                        "self.schedule.step() in Model.step(); map model.steps -> "
                        "schedule.steps. Never poke the private _steps/_advance_time. "
                        "See version-history.md §15c 'sub-3.0 clock trap'."),
        "note": (("CRITICAL: this file calls batch_run, whose 2.x worker loops "
                  "`while model.running and model._steps <= max_steps`; with no scheduler "
                  "`_steps` never advances and every batch_run cell HANGS FOREVER (silent, "
                  "100% CPU — verified on 2.4.0). " if has_batch else
                  "This file uses AgentSet activation with no scheduler; below 3.0 that leaves "
                  "the model clock un-advanced (model.steps does not exist there either). ")
                 + "Activation permutations differ from shuffle_do, so seeded trajectories "
                   "shift — report it."),
        "introduced": "3.0.0", "deprecated": None, "superseded": None, "removed": None,
    })
    return findings


def find_non_python_cells(path: Path):
    """Code cells whose source is not valid Python (magics/shell lines stripped).

    Teaching notebooks routinely hold prose or ASCII-art pattern diagrams
    (`. # # .`) in *code* cells — the author meant markdown. Every linear
    execution then dies there with a SyntaxError that has nothing to do with
    Mesa. Detecting it costs milliseconds, where discovering it by running the
    notebook costs a full pinned install + execution cycle. Reported as
    pre-existing context, never edited: converting the cell would violate the
    structure contract.
    """
    bad = []
    try:
        cells = [(i, src) for i, ctype, src in iter_cells(path) if ctype == "code"]
    except Exception:  # noqa: BLE001
        return bad
    for idx, src in cells:
        body = "\n".join(l for l in src.split("\n")
                         if not l.lstrip().startswith(("!", "%")))
        if not body.strip():
            continue
        try:
            ast.parse(body)
        except SyntaxError:
            first = next((l for l in src.split("\n") if l.strip()), "")
            bad.append({"cell": idx, "text": first.strip()[:80]})
        except Exception:  # noqa: BLE001
            continue
    return bad


def apply_comment_coverage(path: Path, findings, target, entries):
    """Comment-parity check for MIGRATION-INSERTED modern APIs.

    A migration that introduces a construct new at the target (create_agents,
    run_for, SpaceRenderer, CellAgent, rng=...) drops it into a notebook whose
    comments were written for the PREVIOUS idiom — so the new line arrives
    unexplained, or worse, sits under a comment describing the old mechanism.
    For every registry entry flagged `explain:true` whose API is current at the
    target, each code line matching it must have a comment in reach: a trailing
    `#` on the line itself, or a `#` line directly above (blank lines allowed
    between). Uncovered lines surface as ONE `judge` finding per (cell, api) —
    judge, not actionable, because silence is legitimate when it matches the
    notebook's own commenting density (and a markdown cell right above may be
    the explanation). The decision is add / extend / replace / stay-silent,
    made in the author's language, voice and density — never a version
    reference."""
    exp = [e for e in entries
           if e.get("explain") and e.get("introduced")
           and status_at(e, target) == "current"]
    if not exp:
        return findings
    try:
        cells = [(idx, src) for idx, ctype, src in iter_cells(path) if ctype == "code"]
    except Exception:  # noqa: BLE001
        return findings
    seen = set()
    for idx, src in cells:
        lines = src.split("\n")

        def covered(i):
            if "#" in lines[i]:
                return True
            j = i - 1
            while j >= 0 and lines[j].strip() == "":
                j -= 1
            return j >= 0 and lines[j].lstrip().startswith("#")

        def local_density(i, window=3):
            """Does the code AROUND this line carry comments?

            The notebook's own style is the norm, and style is local: a
            well-commented model class can still contain a bare import block or
            a two-line helper the author never annotated. Adding a comment
            there would BREAK parity, not restore it. So only ask the question
            where neighbouring lines show the author was commenting."""
            lo, hi = max(0, i - window), min(len(lines), i + window + 1)
            return any("#" in lines[j] for j in range(lo, hi) if j != i)

        for e in exp:
            for i, ln in enumerate(lines):
                if not any(rx.search(ln) for rx in e["_rx"]):
                    continue
                if covered(i) or not local_density(i):
                    continue
                # One item per uncommented LINE: several registry entries can
                # match the same construct (a discrete_space import matches the
                # module entry and both cell-space class entries) and the
                # decision — comment it or not — is made once.
                if (idx, i) in seen:
                    continue
                seen.add((idx, i))
                findings.append({
                    "file": str(path), "cell": idx, "cell_type": "code",
                    "line_in_cell": i + 1, "text": ln.strip()[:200],
                    "api": "uncommented-new-api", "status": "judge",
                    "replacement": (f"Construct from the {e['id']} entry (introduced "
                                    f"{e.get('introduced')}) with no comment on or above the "
                                    "line. If the notebook comments comparable steps, add or "
                                    "extend a short comment explaining WHAT it does — author's "
                                    "language, voice and density, no version references. If an "
                                    "old comment nearby still describes the pre-migration "
                                    "construct, make it describe this one. If the notebook is "
                                    "sparsely commented or a markdown cell right above explains "
                                    "it, silence is correct — record as a false positive."),
                    "note": "comment-parity check (SKILL.md Step 4): new-at-target API inserted by the migration must be as well explained as the rest of the notebook.",
                    "introduced": e.get("introduced"), "deprecated": e.get("deprecated"),
                    "superseded": e.get("superseded"), "removed": e.get("removed"),
                })
                break
    return findings


def build_ladder(evidence, entries, target):
    """The per-version rung list for THIS file set: for every matched API, the
    lifecycle events the migration must act on — stamps already crossed at the
    target (deprecated/superseded/removed = the upgrade work, each with its
    target-era replacement) and introduced-after-target stamps (the downgrade
    work). This is the 'what happened between the eras, version by version'
    view; oldest rung first."""
    by_id = {e["id"]: e for e in entries}
    rungs = {}
    for mid in {ev["id"] for ev in evidence}:
        e = by_id.get(mid)
        if e is None:
            continue
        eff = effective(e, target)
        repl = (eff[1] if eff is not SUPPRESS else e.get("replacement", ""))
        repl = repl.replace("{TARGET}", target_str_holder[0])
        for field in ("deprecated", "superseded", "removed"):
            v = e.get(field)
            if v and target >= parse_version(v):
                rungs[(v, mid, field)] = repl
        intro = e.get("introduced")
        if intro and target < parse_version(intro):
            rungs[(intro, mid, "introduced-after-target")] = repl
    out = [{"version": v, "api": mid, "event": ev, "replacement": r}
           for (v, mid, ev), r in rungs.items()]
    out.sort(key=lambda r: (parse_version(r["version"]), r["api"]))
    return out


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
    """Return (ok, message, canonical). Hard error on unknown; warn on
    prerelease/uninstallable. `canonical` is the catalog's release string for
    the target ('v3.5.1'/'3.5.1.0'/'03.5.1' all canonicalize to '3.5.1'), so
    every {TARGET} substitution and pin check uses the real version."""
    if catalog is None:
        return True, None, target_str
    rec = catalog.get(target_str)
    if rec is None:
        # normalize (2.1 vs 2.1.0, v-prefix, zero-padding)
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
                       f"(Run scripts/update_catalog.py if Mesa released it recently.)"), target_str
    canonical = rec.get("version", target_str)
    if rec.get("on_pypi") is False:
        return False, (f"Target {target_str!r} is in the changelog but was never "
                       f"uploaded to PyPI — cannot install. {rec.get('note','')}"), canonical
    if rec.get("installable") is False:
        return False, (f"Target {target_str!r} exists on PyPI but has NO files — "
                       f"cannot install. {rec.get('note','')}"), canonical
    if rec.get("prerelease"):
        return True, (f"NOTE: {canonical} is a PRE-RELEASE (breaking, unstable). "
                      f"Proceed only if the user explicitly asked for it."), canonical
    if rec.get("yanked"):
        return True, f"NOTE: {canonical} was YANKED from PyPI — confirm with the user.", canonical
    return True, None, canonical


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
    ok, msg, canonical = validate_target(args.target, catalog)
    if not ok:
        print(msg, file=sys.stderr)
        return 2
    if msg and not args.json:
        print(msg + "\n", file=sys.stderr)
    # canonicalize: '--target v3.5.1' / '3.5.1.0' behave exactly like '3.5.1'
    args.target = canonical
    target_str_holder[0] = canonical
    target = parse_version(canonical)

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

    all_findings, all_evidence, non_python = [], [], []
    for f in args.files:
        path = Path(f)
        if not path.exists():
            print(f"No such file: {path}", file=sys.stderr)
            return 2
        for bad in find_non_python_cells(path):
            non_python.append({"file": str(path), **bad})
        fnd, ev = scan_file(path, entries, target, args.show_current)
        fnd = apply_multiline_entries(path, fnd, target, entries)
        fnd = apply_continuous_keep_rule(path, fnd)
        fnd = apply_batchrun_context(path, fnd, target, entries)
        fnd = apply_cell_space_base_rule(path, fnd, target)
        fnd = apply_pre3_clock_rule(path, fnd, target)
        fnd = apply_comment_coverage(path, fnd, target, entries)
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
    ladder = build_ladder(all_evidence, entries, target)

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
            "ladder": ladder,
            "non_python_code_cells": non_python,
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
        if non_python:
            print(f"\n{len(non_python)} code cell(s) are NOT valid Python (pre-existing, "
                  f"not a Mesa issue) — a linear run dies at the first one with a "
                  f"SyntaxError. Use the extraction path (SKILL.md Step 6) to verify "
                  f"Mesa correctness; never convert or reorder these cells:")
            for b in non_python:
                print(f"  {Path(b['file']).name} cell {b['cell']}: {b['text']!r}")
        if ladder:
            print(f"\nMigration ladder — what changed, version by version, for the "
                  f"APIs matched in these files (replacements are target-{args.target} forms):")
            for r in ladder:
                print(f"  {r['version']:>8}  {r['event']:<24} {r['api']}")
                if r["replacement"]:
                    print(f"            → {r['replacement'][:160]}")
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
