#!/usr/bin/env python3
"""Canonicalize notebooks: nbformat read -> validate -> write, in place.

The mandatory finishing gate after editing. Restores Jupyter's canonical
serialization (list-of-lines sources, indent, trailing newline), erasing
artifacts left by NotebookEdit (single-string sources, cleared trailing
newline) or ad-hoc JSON edits, and fails loudly on schema violations.

With `--original ORIG.ipynb` it also audits the delivered file's EXECUTION
STATE against the pre-edit original and flags contamination left by a run that
did not complete (the extraction path, Step 6):

    ERROR-OUTPUT      a cell stores an `error` output the original did not have
                      — a traceback students would read as the notebook's own
                      result (a cell that teaches an error has it in the
                      original too, and is not flagged)
    PARTIAL-RUN       the file carries an aborted run: some code cells got an
                      execution_count the original had as null while other
                      non-empty code cells are still null. A complete linear
                      run numbers every cell, so it stays silent here

Restore every flagged cell to the original's `execution_count`/`outputs` — on
that path the original's outputs are the only correct ones.

Usage:
    uv run --with nbformat python normalize_notebook.py NB.ipynb [MORE.ipynb ...]
    uv run --with nbformat python normalize_notebook.py NB.ipynb --original ORIG.ipynb

Exit codes: 0 = all normalized and valid; 3 = at least one validation error
(file is still written so you can inspect it); 4 = execution contamination.
"""
import argparse
import sys

import nbformat


def code_cells(nb):
    """Code cells as (id_or_None, cell), in order."""
    return [(c.get("id"), c) for c in nb.cells if c.get("cell_type") == "code"]


def align(orig, migr):
    """Yield (orig_cell_or_None, migr_cell, key) over code cells.

    Aligns by cell id when both files carry ids on every code cell; otherwise
    by index — same rule as check_text_delta.py."""
    o_ids, m_ids = [i for i, _ in orig], [i for i, _ in migr]
    by_id = (all(o_ids) and all(m_ids)
             and len(set(o_ids)) == len(o_ids) and len(set(m_ids)) == len(m_ids))
    if by_id:
        om = dict(orig)
        for cid, c in migr:
            yield om.get(cid), c, cid
    else:
        for i, (_, c) in enumerate(migr):
            yield (orig[i][1] if i < len(orig) else None), c, i


def has_error(cell):
    return any(o.get("output_type") == "error"
               for o in (cell.get("outputs") or []))


def check_execution_state(orig_nb, migr_nb):
    """Flags for run contamination in MIGR that the ORIGINAL does not carry.

    Two surfaces, both invisible to a text or API diff. The error check is
    per-cell against the original, so a cell that demonstrates a traceback on
    purpose (error output already in the original) never fires. The
    execution_count check fires only on a PARTIAL run, because a complete
    linear run legitimately numbers every code cell from null."""
    flags = []
    pairs = list(align(code_cells(orig_nb), code_cells(migr_nb)))
    fresh_counts, still_null = [], []
    for o, m, key in pairs:
        if has_error(m) and not (o is not None and has_error(o)):
            flags.append(("ERROR-OUTPUT", key,
                          "stores an `error` output the original does not have"))
        o_count = o.get("execution_count") if o is not None else None
        if m.get("execution_count") is not None and o_count is None:
            fresh_counts.append(key)
        elif m.get("execution_count") is None and "".join(m.get("source", "")).strip():
            still_null.append(key)
    if fresh_counts and still_null:
        flags.append(("PARTIAL-RUN", ",".join(str(k) for k in fresh_counts),
                      f"execution_count set by a run that left {len(still_null)} "
                      f"non-empty code cell(s) unexecuted — the run did not complete"))
    return flags


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("notebooks", nargs="+")
    ap.add_argument("--original", default=None,
                    help="pre-edit original (git show HEAD:… or the Step-4 "
                         "snapshot) — audits the delivered execution state "
                         "against it; one notebook at a time")
    args = ap.parse_args()

    if args.original and len(args.notebooks) != 1:
        print("--original takes exactly one notebook", file=sys.stderr)
        return 2

    status = 0
    for path in args.notebooks:
        nb = nbformat.read(path, as_version=4)
        try:
            nbformat.validate(nb)
        except nbformat.ValidationError as exc:
            first_line = str(exc).splitlines()[0] if str(exc) else repr(exc)
            print(f"{path}: VALIDATION ERROR: {first_line}")
            status = 3
        nbformat.write(nb, path)
        print(f"{path}: normalized")
        if args.original:
            orig = nbformat.read(args.original, as_version=4)
            flags = check_execution_state(orig, nb)
            for kind, key, msg in flags:
                print(f"{path}: [{kind}] cell {key}: {msg}")
            if flags:
                print(f"{path}: restore the flagged cells' execution_count/outputs "
                      "to the original's — a delivered notebook must never carry "
                      "output from a run that did not complete")
                status = status or 4
            else:
                print(f"{path}: execution state clean against {args.original}")
    return status


if __name__ == "__main__":
    sys.exit(main())
