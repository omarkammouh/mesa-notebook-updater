#!/usr/bin/env python3
"""Verify the Step-7 report's FACTS BLOCK against the file it claims to describe.

The report is the only thing the lecturer reads, and prose is not checkable: a
fabricated number reads exactly like a true one, and the honest phrasings the
skill asks for ("left as-is", "outputs in cells 4 and 9 were cleared") look like
lies to any pattern matcher. So this script never reads the prose. Instead the
report must carry ONE fenced block — the claim of record — holding only facts
the delivered file can settle, and each line of that block is re-derived from
the artifact:

    ```mesa-report-facts
    target: 3.5.1
    file: nb_21e4.ipynb
    execution: linear-green
    warnings_in_outputs: 0
    error_outputs: none
    output_cells: 1,3,5,7
    outputs: regenerated
    actionable_count: 0
    judge_count: 5
    language_info.version: 3.12.12
    kernelspec.name: python3
    kernelspec.display_name: Python 3
    widgets_metadata: absent
    cells_before: 8
    cells_after: 8
    output_quote: Occupied cells: 18
    ```

Every field is re-derived and reported as **agree**, **DISAGREE** or
**unverifiable** (the artifact cannot settle it from what was passed in — e.g.
`cells_before` without `--original`). Paraphrasing the surrounding prose changes
nothing: the block is what is checked. Deleting or mangling the block is not a
free pass — that exits 2.

Fields, and what settles each:

    target                  parses; equals --target when given
    file                    basename of the delivered file
    execution               linear-green | extraction | blocked; a linear-green
                            claim is contradicted by a stored error output
    warnings_in_outputs     count of Future/Deprecation/UserWarning occurrences
                            in the delivered file's stored outputs, subclass
                            names included (MatplotlibDeprecationWarning counts).
                            A total, not a Mesa-only count: whether any of them
                            are Mesa's — the thing that decides whether the
                            migration is finished — belongs in report item 7
    error_outputs           `none` or the cell indices storing an error output
    output_cells            `none` or the cells carrying outputs / an
                            execution_count (states partial clearing exactly)
    outputs                 cleared (no such cells) | regenerated (some) |
                            preserved (identical to --original) | mixed
    actionable_count        scan_notebook.py at the target (O1)
    judge_count             scan_notebook.py at the target (O5)
    language_info.version   notebook metadata, or `absent`
    kernelspec.name         notebook metadata, or `absent`
    kernelspec.display_name notebook metadata, or `absent`
    widgets_metadata        `absent` or `present:N` (N = widget states)
    cells_before            cell count of --original
    cells_after             cell count of the delivered file
    output_quote            repeatable, optional: a literal the report presents
                            as a run result — must appear verbatim (whitespace-
                            normalized) in some stored output of the file

For a `.py` input the notebook-only fields take the literal value `n-a`. A line
may carry a trailing ` # comment` (stripped on every field but `output_quote`,
whose value is a stored-output literal that may itself contain `#`).

The block must be *the* claim of record, and must be the one a human reader
actually sees, so placement is checked too (fail-closed, exit 2):

    * a claim block is any fence — ``` or ~~~, three chars or more — whose info
      string is `mesa-report-facts`. A 4-backtick or tilde block is a claim
      block, not a decoy that the checker looks past.
    * exactly one claim block may exist, in any fence form.
    * it must be plainly visible: a claim block inside an HTML comment is
      invisible to the reader and is an error, not a valid block.
    * it must sit immediately before the digest — only blank lines and markdown
      headings may separate them, and the digest must be the final fenced block.

What this does NOT do: the prose is never checked. Two attempts to verify it —
regex over the whole narrative, and a narrowly-anchored cross-check of only the
claims the artifact had already settled — each rejected honest reports, and a
gate that blocks correct work is worse than the defect it replaces. Verifying
free prose is a semantic task, out of scope here. The block sits immediately
before the digest so a reader sees claim and summary together, and every number
in the prose or the digest must be copied from the block.

Advisory (printed, never fatal — truthful reports breach it today):

    DIGEST-LENGTH   the Step-7 digest is longer than the ~6-line cap
    UNKNOWN-KEY     a key not in the schema (usually a typo)

Usage:  check_report.py REPORT.md MIGRATED.ipynb [--original ORIG.ipynb]
                        [--target X.Y.Z] [--json] [--scanner PATH]

Exit: 0 = every field agrees; 1 = at least one DISAGREE; 2 = missing/malformed
block, or bad input. Stdlib only. Python 3.9+.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SCANNER = HERE / "scan_notebook.py"
sys.path.insert(0, str(HERE))
from mesa_versions import parse_version  # noqa: E402

BLOCK_NAME = "mesa-report-facts"
FENCE_OPEN_RX = re.compile(r"^(?P<indent>[ \t]*)(?P<fence>`{3,}|~{3,})[ \t]*"
                           r"(?P<info>[^\n]*?)[ \t]*$")
HTML_COMMENT_RX = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
HEADING_ONLY_RX = re.compile(r"^[ \t]*(?:#{1,6}[ \t].*)?$")

# Subclass names count: MatplotlibDeprecationWarning IS a warning stored in the
# outputs, and a report that says 0 while nine of them sit in a cell is wrong.
# Kept identical to run_notebook.WARN_LINE minus RuntimeWarning (numeric noise,
# not a migration signal) so the runner and this checker mean the same thing by
# "a warning" — they disagreeing is what made an honest count read as a lie.
WARNING_RX = re.compile(r"\b\w*(?:Future|Deprecation|User)Warning\b")

SINGLE_KEYS = [
    "target", "file", "execution", "warnings_in_outputs", "error_outputs",
    "output_cells", "outputs", "actionable_count", "judge_count",
    "language_info.version", "kernelspec.name", "kernelspec.display_name",
    "widgets_metadata", "cells_before", "cells_after",
]
REPEATABLE_KEYS = ["output_quote"]
NOTEBOOK_ONLY = {"output_cells", "outputs", "language_info.version",
                 "kernelspec.name", "kernelspec.display_name",
                 "widgets_metadata", "cells_before", "cells_after",
                 "error_outputs", "warnings_in_outputs"}
EXECUTION_VALUES = {"linear-green", "extraction", "blocked"}
OUTPUTS_VALUES = {"cleared", "regenerated", "preserved", "mixed"}
NA = "n-a"


# --------------------------------------------------------------------------
# parsing


class Fence:
    """One fenced block: its info string, body, and where it sits."""

    def __init__(self, info, body, first_line, last_line, start, end):
        self.info = info
        self.body = body
        self.first_line = first_line   # index of the opening fence line
        self.last_line = last_line     # index of the closing fence line (or EOF)
        self.start = start             # char offset of the opening fence
        self.end = end                 # char offset just past the closing fence

    @property
    def is_claim(self):
        return self.info.strip() == BLOCK_NAME


def scan_fences(report):
    """Every fenced block in the report, whatever the fence char and length.

    A hand-rolled scanner rather than one regex: the whole point is that a
    ~~~-fenced or 4-backtick block is not invisible to us the way it was to a
    ```-only pattern.
    """
    lines = report.split("\n")
    offsets, pos = [], 0
    for ln in lines:
        offsets.append(pos)
        pos += len(ln) + 1
    fences, i = [], 0
    while i < len(lines):
        m = FENCE_OPEN_RX.match(lines[i])
        if not m:
            i += 1
            continue
        char, length = m.group("fence")[0], len(m.group("fence"))
        if char == "`" and "`" in m.group("info"):
            i += 1  # not a fence: inline code, per CommonMark
            continue
        close_rx = re.compile(r"^[ \t]*" + re.escape(char) + "{%d,}[ \t]*$" % length)
        j = i + 1
        while j < len(lines) and not close_rx.match(lines[j]):
            j += 1
        body = "\n".join(lines[i + 1:j])
        end = offsets[j] + len(lines[j]) if j < len(lines) else len(report)
        fences.append(Fence(m.group("info"), body, i, min(j, len(lines) - 1),
                            offsets[i], end))
        i = j + 1
    return fences


def comment_spans(report):
    return [(m.start(), m.end()) for m in HTML_COMMENT_RX.finditer(report)]


def inside(span_list, start, end):
    return any(s <= start and end <= e for s, e in span_list)


def locate_block(report):
    """(claim_fence, all_fences, error) — fail closed on anything ambiguous."""
    fences = scan_fences(report)
    claims = [f for f in fences if f.is_claim]
    hidden = comment_spans(report)
    if not claims:
        return None, fences, (
            f"no {BLOCK_NAME} block in the report — Step 7 requires it; "
            "without it nothing in the report is checkable")
    if len(claims) > 1:
        forms = ", ".join(sorted({f.info.strip() and f"line {f.first_line + 1}"
                                  for f in claims}))
        return None, fences, (
            f"{len(claims)} {BLOCK_NAME} blocks ({forms}) — there must be "
            "exactly one claim of record, counting every fence form (``` , "
            "~~~, 4+ backticks) and every position, visible or commented out")
    claim = claims[0]
    if inside(hidden, claim.start, claim.end):
        return None, fences, (
            f"the {BLOCK_NAME} block sits inside an HTML comment — it is "
            "invisible in the rendered report, so it is not a claim anyone "
            "reads; the claim of record must be plainly visible")
    idx = fences.index(claim)
    following = [f for f in fences[idx + 1:]
                 if not inside(hidden, f.start, f.end)]
    if not following:
        return None, fences, (
            f"the {BLOCK_NAME} block is not followed by a digest block — "
            "Step 7 puts the facts block immediately before the digest")
    digest = following[0]
    if digest is not fences[-1]:
        return None, fences, (
            "the digest must be the last fenced block in the report, with the "
            f"{BLOCK_NAME} block immediately before it")
    between = report.split("\n")[claim.last_line + 1:digest.first_line]
    if any(not HEADING_ONLY_RX.match(ln) for ln in between):
        return None, fences, (
            f"the {BLOCK_NAME} block must sit immediately before the digest — "
            "only blank lines and headings may come between them, but there is "
            "prose in the gap")
    return claim, fences, None


def parse_block(report):
    """(fields, repeated, error). fields maps key -> value for the single-valued
    keys; repeated maps key -> [values]. error is a human message when the block
    is missing, duplicated, hidden, misplaced or malformed."""
    claim, _fences, err = locate_block(report)
    if err:
        return None, None, err
    fields, repeated, bad = {}, {k: [] for k in REPEATABLE_KEYS}, []
    for raw in claim.body.split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            bad.append(f"line is not `key: value`: {line!r}")
            continue
        key, val = line.split(":", 1)
        key, val = key.strip(), val.strip()
        if key not in REPEATABLE_KEYS:
            # a trailing ` # …` is a comment on every field except output_quote,
            # whose value is a stored-output literal that may itself contain '#'
            val = re.split(r"\s+#", val)[0].strip()
        if key in REPEATABLE_KEYS:
            repeated[key].append(val)
        elif key in SINGLE_KEYS:
            if key in fields:
                bad.append(f"duplicate key {key!r}")
            fields[key] = val
        else:
            fields.setdefault("__unknown__", []).append(key)
    missing = [k for k in SINGLE_KEYS if k not in fields]
    if missing:
        bad.append("missing required key(s): " + ", ".join(missing))
    if bad:
        return None, None, "; ".join(bad)
    return fields, repeated, None


def digest_fence(report):
    """The Step-7 item-8 digest: the last visible fenced block that is not the
    facts block."""
    hidden = comment_spans(report)
    for f in reversed(scan_fences(report)):
        if f.is_claim or inside(hidden, f.start, f.end):
            continue
        return f
    return None


def digest_lines(report):
    f = digest_fence(report)
    return None if f is None else [ln for ln in f.body.split("\n") if ln.strip()]


# --------------------------------------------------------------------------
# derivation from the artifact


def load_nb(path):
    if path.suffix != ".ipynb":
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def stored_outputs(nb):
    """(cell_index, text) for every stored output — the file's own record of
    what it printed."""
    for i, cell in enumerate(nb.get("cells", [])):
        for out in cell.get("outputs", []) or []:
            parts = []
            val = out.get("text")
            if val:
                parts.append("".join(val) if isinstance(val, list) else val)
            data = out.get("data") or {}
            for mime in ("text/plain", "text/html", "text/markdown"):
                val = data.get(mime)
                if val:
                    parts.append("".join(val) if isinstance(val, list) else val)
            tb = out.get("traceback")
            if tb:
                parts.append("\n".join(tb) if isinstance(tb, list) else tb)
            for key in ("ename", "evalue"):
                if out.get(key):
                    parts.append(str(out[key]))
            if parts:
                yield i, "\n".join(parts)


def error_cells(nb):
    return [i for i, c in enumerate(nb.get("cells", []))
            if any((o or {}).get("output_type") == "error"
                   for o in c.get("outputs", []) or [])]


def executed_cells(nb):
    """Cells carrying stored outputs or an execution_count — everything a
    "cleared" claim has to be empty of."""
    return [i for i, c in enumerate(nb.get("cells", []))
            if (c.get("outputs") or []) or c.get("execution_count") is not None]


def exec_state(nb):
    return [(c.get("execution_count"), c.get("outputs") or [])
            for c in nb.get("cells", [])]


def meta_value(nb, path):
    val = nb.get("metadata", {}).get(path[0], {})
    if not isinstance(val, dict):
        return None
    return val.get(path[1])


def widget_states(nb):
    """None when metadata.widgets is absent, else the number of widget states."""
    widgets = nb.get("metadata", {}).get("widgets")
    if widgets is None:
        return None
    if not isinstance(widgets, dict):
        return 0
    state = widgets.get(
        "application/vnd.jupyter.widget-state+json", {}) or {}
    return len(state.get("state", {}) or {})


def norm_ws(text):
    return re.sub(r"\s+", " ", text).strip()


def contains_literal(blob, needle):
    """`needle` occurs in `blob` and is not a truncation of a longer token.

    Plain substring matching let `Occupied cells: 1` pass against a stored
    `Occupied cells: 18` — a quote that means something else entirely. The match
    must be bounded on both sides by a non-alphanumeric character.
    """
    if not needle:
        return False
    at = blob.find(needle)
    while at != -1:
        before = blob[at - 1] if at else ""
        after = blob[at + len(needle):at + len(needle) + 1]
        if not (before.isalnum() and needle[0].isalnum()) and \
           not (after.isalnum() and needle[-1].isalnum()):
            return True
        at = blob.find(needle, at + 1)
    return False


def parse_index_list(val):
    """`none` / `1,3,5` / `1 3 5` -> list of ints, or None when unparseable."""
    if val.lower() in ("none", "[]", ""):
        return []
    try:
        return sorted(int(p) for p in re.split(r"[,\s]+", val.strip("[]")) if p)
    except ValueError:
        return None


def scanner_counts(scanner, migrated, target):
    """(actionable_count, judge_count) from the scanner at the target, or
    (None, None) if it could not be run."""
    cmd = [sys.executable, str(scanner), str(migrated), "--target", target,
           "--json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        data = json.loads(proc.stdout)
    except Exception:  # noqa: BLE001
        return None, None
    return data.get("actionable_count"), data.get("judge_count")


# --------------------------------------------------------------------------
# the checks


class Fields:
    """Collects one verdict per block field."""

    def __init__(self):
        self.rows = []

    def agree(self, key, stated, detail=""):
        self.rows.append({"field": key, "verdict": "agree", "stated": stated,
                          "detail": detail})

    def disagree(self, key, stated, detail):
        self.rows.append({"field": key, "verdict": "DISAGREE", "stated": stated,
                          "detail": detail})

    def unverifiable(self, key, stated, detail):
        self.rows.append({"field": key, "verdict": "unverifiable",
                          "stated": stated, "detail": detail})

    def compare(self, key, stated, actual, render=str):
        """The common case: a stated value against the derived one."""
        if stated == render(actual):
            self.agree(key, stated)
        else:
            self.disagree(key, stated, f"the file has `{render(actual)}`")

    @property
    def disagreements(self):
        return [r for r in self.rows if r["verdict"] == "DISAGREE"]

    @property
    def unverified(self):
        return [r for r in self.rows if r["verdict"] == "unverifiable"]


def check_int(fields_out, key, stated, actual, source):
    try:
        want = int(stated)
    except ValueError:
        fields_out.disagree(key, stated, "not an integer")
        return
    if actual is None:
        fields_out.unverifiable(key, stated, f"{source} unavailable")
    elif want == actual:
        fields_out.agree(key, stated)
    else:
        fields_out.disagree(key, stated, f"{source} reports {actual}")


def verify(block, quotes, nb, orig, migrated_path, target_arg, scanner):
    out = Fields()

    # --- target -----------------------------------------------------------
    stated_target = block["target"]
    try:
        parsed = parse_version(stated_target)
    except ValueError as exc:
        out.disagree("target", stated_target, f"unparseable version ({exc})")
        parsed = None
    if parsed is not None:
        if target_arg is None:
            out.unverifiable("target", stated_target,
                             "no --target passed to compare against")
        elif parse_version(target_arg) == parsed:
            out.agree("target", stated_target)
        else:
            out.disagree("target", stated_target,
                         f"the gate was run at --target {target_arg}")

    # --- file -------------------------------------------------------------
    out.compare("file", block["file"], migrated_path.name)

    scan_target = target_arg or (stated_target if parsed else None)
    actionable = judge = None
    if scan_target:
        actionable, judge = scanner_counts(scanner, migrated_path, scan_target)
    check_int(out, "actionable_count", block["actionable_count"], actionable,
              "the scanner")
    check_int(out, "judge_count", block["judge_count"], judge, "the scanner")

    if nb is None:  # .py input — the notebook-only fields must say so
        for key in sorted(NOTEBOOK_ONLY):
            stated = block[key]
            if stated.lower() == NA:
                out.agree(key, stated, "not applicable to a .py input")
            else:
                out.disagree(key, stated,
                             f"the delivered file is not a notebook — say `{NA}`")
        out.unverifiable("execution", block["execution"],
                         ".py input stores no execution state")
        for lit in quotes:
            out.unverifiable("output_quote", lit,
                             ".py input carries no stored outputs")
        return out

    for key in sorted(NOTEBOOK_ONLY):
        if block[key].lower() == NA:
            out.disagree(key, block[key],
                         "the delivered file IS a notebook — state the real value")

    blobs = list(stored_outputs(nb))
    errs = error_cells(nb)
    execd = executed_cells(nb)

    # --- error_outputs ----------------------------------------------------
    stated_errs = parse_index_list(block["error_outputs"])
    if block["error_outputs"].lower() != NA:
        if stated_errs is None:
            out.disagree("error_outputs", block["error_outputs"],
                         "not `none` or a list of cell indices")
        elif stated_errs == errs:
            out.agree("error_outputs", block["error_outputs"])
        else:
            out.disagree("error_outputs", block["error_outputs"],
                         f"the file stores error outputs in cells {errs or 'none'}")

    # --- execution --------------------------------------------------------
    mode = block["execution"].lower()
    if mode not in EXECUTION_VALUES:
        out.disagree("execution", block["execution"],
                     "not one of " + " | ".join(sorted(EXECUTION_VALUES)))
    elif mode == "linear-green":
        if errs:
            out.disagree("execution", block["execution"],
                         f"cell {errs[0]} of the delivered file stores an error "
                         "output — a green run cannot leave one")
        else:
            out.agree("execution", block["execution"],
                      "no stored error output contradicts it")
    else:
        out.unverifiable("execution", block["execution"],
                         "only a linear-green claim is falsifiable from the file")

    # --- warnings_in_outputs ---------------------------------------------
    if block["warnings_in_outputs"].lower() != NA:
        found = sum(len(WARNING_RX.findall(b)) for _, b in blobs)
        check_int(out, "warnings_in_outputs", block["warnings_in_outputs"],
                  found, "the stored outputs")

    # --- output_cells / outputs ------------------------------------------
    stated_cells = parse_index_list(block["output_cells"])
    if block["output_cells"].lower() != NA:
        if stated_cells is None:
            out.disagree("output_cells", block["output_cells"],
                         "not `none` or a list of cell indices")
        elif stated_cells == execd:
            out.agree("output_cells", block["output_cells"])
        else:
            out.disagree("output_cells", block["output_cells"],
                         "cells carrying outputs or an execution_count are "
                         f"{execd or 'none'}")

    disp = block["outputs"].lower()
    if disp == NA:
        pass
    elif disp not in OUTPUTS_VALUES:
        out.disagree("outputs", block["outputs"],
                     "not one of " + " | ".join(sorted(OUTPUTS_VALUES)))
    elif disp == "cleared":
        if execd:
            out.disagree("outputs", block["outputs"],
                         f"cells {execd} still carry outputs or an execution_count")
        else:
            out.agree("outputs", block["outputs"])
    elif disp == "regenerated":
        if execd:
            out.agree("outputs", block["outputs"])
        else:
            out.disagree("outputs", block["outputs"],
                         "no cell carries an output or an execution_count")
    elif disp == "preserved":
        if orig is None:
            out.unverifiable("outputs", block["outputs"],
                             "needs --original to compare execution state")
        elif exec_state(orig) == exec_state(nb):
            out.agree("outputs", block["outputs"])
        else:
            out.disagree("outputs", block["outputs"],
                         "the execution state differs from the original")
    else:  # mixed — output_cells carries the exact claim
        out.agree("outputs", block["outputs"], "exactness carried by output_cells")

    # --- metadata ---------------------------------------------------------
    for key, path in (("language_info.version", ("language_info", "version")),
                      ("kernelspec.name", ("kernelspec", "name")),
                      ("kernelspec.display_name", ("kernelspec", "display_name"))):
        if block[key].lower() == NA:
            continue
        actual = meta_value(nb, path)
        out.compare(key, block[key], actual,
                    render=lambda v: "absent" if v is None else str(v))

    if block["widgets_metadata"].lower() != NA:
        states = widget_states(nb)
        actual = "absent" if states is None else f"present:{states}"
        stated = block["widgets_metadata"]
        if stated.lower() == "present" and states is not None:
            out.agree("widgets_metadata", stated,
                      f"present ({states} widget state(s))")
        else:
            out.compare("widgets_metadata", stated, actual, render=lambda v: v)

    # --- cell counts ------------------------------------------------------
    if block["cells_after"].lower() != NA:
        check_int(out, "cells_after", block["cells_after"],
                  len(nb.get("cells", [])), "the delivered file")
    if block["cells_before"].lower() != NA:
        check_int(out, "cells_before", block["cells_before"],
                  len(orig.get("cells", [])) if orig else None,
                  "the original (--original)")

    # --- output_quote -----------------------------------------------------
    flat = [norm_ws(b) for _, b in blobs]
    for lit in quotes:
        needle = norm_ws(lit)
        if not needle:
            continue
        if any(contains_literal(blob, needle) for blob in flat):
            out.agree("output_quote", lit)
        elif any(needle in blob for blob in flat):
            out.disagree("output_quote", lit,
                         "only occurs inside a longer token in the stored "
                         "outputs — the quote is truncated, so it states a "
                         "different result than the file holds")
        else:
            out.disagree("output_quote", lit,
                         "no stored output of the delivered file contains it")

    return out


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("migrated")
    ap.add_argument("--original", default=None,
                    help="pre-edit original (git show HEAD:… or the Step-4 "
                         "snapshot) — settles cells_before and outputs: preserved")
    ap.add_argument("--target", default=None,
                    help="Mesa target version — settles target and lets the "
                         "scanner settle actionable_count / judge_count")
    ap.add_argument("--scanner", default=str(DEFAULT_SCANNER))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rp, mp = Path(args.report), Path(args.migrated)
    for p in (rp, mp):
        if not p.exists():
            print(f"No such file: {p}", file=sys.stderr)
            return 2
    if args.target:
        try:
            parse_version(args.target)
        except ValueError as exc:
            print(f"Bad --target: {exc}", file=sys.stderr)
            return 2
    try:
        report = rp.read_text(encoding="utf-8")
        nb = load_nb(mp)
        orig = load_nb(Path(args.original)) if args.original else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"Unreadable input: {exc}", file=sys.stderr)
        return 2

    block, quotes, err = parse_block(report)
    if err:
        if args.json:
            print(json.dumps({"block": "MISSING-OR-MALFORMED", "error": err,
                              "disagree_count": None}, indent=1))
        else:
            print(f"Report audit: {rp.name} vs {mp.name}\n")
            print(f"[BLOCK              ] {err}")
            print("\nThe facts block is the claim of record — a report without a "
                  "well-formed one cannot pass this gate.")
        return 2

    unknown = block.pop("__unknown__", [])
    out = verify(block, quotes["output_quote"], nb, orig, mp, args.target,
                 Path(args.scanner))

    advisories = []
    for key in unknown:
        advisories.append({"kind": "UNKNOWN-KEY",
                           "msg": f"`{key}` is not a facts-block key — typo?"})
    digest = digest_lines(report)
    if digest is None:
        advisories.append({"kind": "DIGEST-LENGTH",
                           "msg": "no digest block found — Step 7 item 8 requires "
                                  "the digest, always last, always present"})
    elif len(digest) > 6:
        advisories.append({"kind": "DIGEST-LENGTH",
                           "msg": f"digest is {len(digest)} lines; Step 7 item 8 "
                                  "caps it at ~6 — the digest is what the user "
                                  "actually reads"})

    if args.json:
        print(json.dumps({"disagree_count": len(out.disagreements),
                          "unverifiable_count": len(out.unverified),
                          "advisory_count": len(advisories),
                          "fields": out.rows,
                          "advisories": advisories}, indent=1))
    else:
        print(f"Report audit: {rp.name} vs {mp.name}\n")
        for row in out.rows:
            detail = f" — {row['detail']}" if row["detail"] else ""
            print(f"[{row['verdict']:12s}] {row['field']}: "
                  f"{row['stated']!r}{detail}")
        for adv in advisories:
            print(f"[{'advisory':12s}] {adv['kind']}: {adv['msg']}")
        print(f"\n{len(out.disagreements)} field(s) the delivered file "
              f"contradicts; {len(out.unverified)} unverifiable; "
              f"{len(advisories)} advisory.")
        if not out.disagreements:
            print("Clean: every fact the block states is re-derived from the file.")
    return 1 if out.disagreements else 0


if __name__ == "__main__":
    sys.exit(main())
