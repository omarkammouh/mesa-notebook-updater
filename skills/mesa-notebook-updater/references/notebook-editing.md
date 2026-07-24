# Processing Jupyter notebooks cleanly

How to read, edit, and write `.ipynb` files without corrupting them, bloating
diffs, or drowning in embedded outputs. Follow this for every notebook touched.

## Anatomy you must preserve

A notebook is JSON: `{"cells": [...], "metadata": {...}, "nbformat": 4, "nbformat_minor": N}`.
Each cell has `cell_type` (`code` | `markdown` | `raw`), `source`, `metadata`,
and — for code cells — `execution_count` and `outputs`.

Non-negotiables when editing:

- **Never regenerate the file wholesale.** Load JSON, mutate only the cells you
  are changing, dump back. Everything else — cell `id`s, cell `metadata`,
  notebook `metadata` (kernelspec, language_info), `nbformat_minor` — passes
  through untouched. Changed ids break git diffs and grading tools.
- **`source` may be a string or a list of strings.** Handle both on read.
  On write, keep the representation the cell already used (Jupyter's own
  convention is a list of lines, each ending `\n` except possibly the last).
- **Preserve trailing-newline conventions** inside `source` exactly; a missing
  `\n` on a joined line silently glues two statements together.
- **Write with `json.dump(nb, f, indent=1, ensure_ascii=False)` + a trailing
  newline** — that matches Jupyter's own serialization, so the only diff is
  your actual edit. (When available, `nbformat.write` handles this for you and
  also validates.)
- **Don't strip outputs** unless the user asks — or Step 6's stale-output rule
  applies (an unexecuted cell whose stored output shows a dead API): teaching notebooks are often
  distributed with outputs visible. Executing at the end regenerates them
  anyway.

## Reading big notebooks (embedded outputs, 1–30 MB)

Course notebooks carry megabytes of base64 PNGs inside `outputs`. Never read
the raw file into context. Instead:

1. **Inventory first** — cell index, type, first line, source size:
   ```bash
   python3 -c "
   import json,sys
   nb=json.load(open(sys.argv[1]))
   for i,c in enumerate(nb['cells']):
       src=''.join(c['source']) if isinstance(c['source'],list) else c['source']
       first=(src.splitlines() or [''])[0]
       print(f\"{i:3d} {c['cell_type']:8s} {len(src):6d}  {first[:80]}\")
   " notebook.ipynb
   ```
2. **Extract sources only** (all cells, numbered) into a temp `.txt` and read
   that; it is the whole notebook minus outputs.
3. **Target single cells** by index when editing.

## Editing rules

- Edit cell `source` only; leave `execution_count`/`outputs` alone (execution
  refreshes them).
- Match indentation and quoting exactly as found; these files are diffed by
  teachers and tools.
- After every batch of edits, validate: `python3 -m json.tool notebook.ipynb
  > /dev/null` (or `nbformat.validate`) before moving on — catching a JSON slip
  immediately beats debugging a corrupted notebook later.
- The `NotebookEdit` tool (when available) is convenient for cell-level edits,
  but know its measured behavior: on replace it writes the cell's `source` as a
  **single string** (not list-of-lines), **clears that cell's outputs**, nulls
  its `execution_count`, and drops the file's trailing newline. That's fine
  *only because* this workflow always ends with execution + the finishing gate
  below; never treat a NotebookEdit-touched file as final without them.
  **NotebookEdit addresses a cell by its `id`, so it cannot target cells in an
  id-less pre-4.5 notebook** (`nbformat_minor < 5` — common for older
  Colab-era notebooks; check with `any('id' in c for c in nb['cells'])`). Adding ids
  to reach them would violate minimal-delta. For those notebooks, use the
  Python-script path (next bullets) — read the JSON, edit `cells[i]["source"]`
  in place (keep it a list of lines), write back — which also preserves outputs
  and the list-of-lines source that NotebookEdit would flatten.
- Cells contain IPython, not pure Python: `%magics`, `%%cell-magics`, and
  `!shell` lines crash `ast`-based tooling. Process sources as text; `%pip`/
  `!pip` lines are data (and, here, migration targets).
- For repetitive changes across many cells (e.g. the same stale comment in 7
  places), write one small Python script that loops over cells and applies the
  exact transformation — deterministic, reviewable, and identical everywhere.
- Code and markdown cells are the main migration surface, and `raw` cells are
  prose surface too: the scanner scans them with the markdown-scope patterns, so
  a stale API name in a raw cell is a real finding — fix the text while keeping
  the cell's type and format fields untouched.
- Widget leftovers: a `metadata.widgets` block without proper `state` fails
  validation and GitHub rendering, and `application/vnd.jupyter.widget-view+json`
  outputs (e.g. SolaraViz) can't re-render without live state — re-executing
  the notebook regenerates or clears these; if widgets metadata still blocks
  validation afterwards, delete the `metadata.widgets` block.

## Finishing gate (mandatory, per notebook)

Run this after the last edit and the final execution, before declaring done:

1. **Canonicalize**: `uv run --with nbformat python scripts/normalize_notebook.py
   notebook.ipynb --original /tmp/orig.ipynb` — a `read → validate → write`
   round-trip through `nbformat` that restores Jupyter's canonical serialization
   (list-of-lines sources, indent, trailing newline), erasing artifacts left by
   NotebookEdit or ad-hoc JSON edits. It fails loudly on schema violations
   (exit 3). With `--original` it also audits the delivered execution state
   against the pre-edit original and exits 4 on contamination from a run that
   did not complete: `ERROR-OUTPUT` (a stored traceback the original did not
   have) or `PARTIAL-RUN` (an `execution_count` written while other non-empty
   code cells were left unexecuted). Restore the flagged cells'
   `execution_count`/`outputs` to the original's. A cell that demonstrates a
   traceback on purpose has that error in the original too, so it never fires;
   nor does a complete linear run, which numbers every code cell.
2. **Prove the minimal diff** (the original is in git — the in-place/no-backup
   policy assumes that): 
   ```bash
   git show HEAD:path/to/notebook.ipynb > /tmp/orig.ipynb
   uv run --with nbdime nbdiff --ignore-outputs /tmp/orig.ipynb path/to/notebook.ipynb
   ```
   Read the diff and check both directions: every hunk maps to a migration
   finding or a modernization-checklist item (no drive-by rewording — markdown
   hunks must satisfy the minimal-delta text contract), and every finding you
   fixed shows up. Without git, diff against wherever the pre-edit original
   still exists; only skip the proof if there is genuinely no original to
   compare against.
3. **Batch acceptance** (when a whole course folder was migrated):
   `uv run --with pytest --with nbmake --with "mesa[rec]==X.Y.Z" pytest --nbmake *.ipynb`
   executes every notebook as a test and gives a one-screen pass/fail table.

## Executing

Use the bundled runner (`scripts/run_notebook.py`) rather than
`jupyter nbconvert --execute`: it executes in place, prints the first error
compactly (cell number, source excerpt, traceback tail), enforces a per-cell
timeout, and surfaces DeprecationWarnings that IPython normally hides.

Run it inside an ephemeral pinned environment so the kernel sees exactly the
target Mesa:

```bash
uv run --python 3.12 --with "mesa[rec]==X.Y.Z" --with nbclient --with ipykernel \
  python scripts/run_notebook.py notebook.ipynb --timeout 120
```

Add `--with` entries for anything else the notebook imports (seaborn,
networkx, …) — check the import cells first. The kernel's working directory is
the notebook's own directory, so local `.py` imports resolve.

## Markdown cells are content, not decoration

In teaching notebooks the markdown *is* the lesson. When code semantics change,
the adjacent explanation almost certainly mentions the old mechanism — check
the cells directly above and below any edited code cell, plus any "theory"
section earlier in the notebook that introduces the API. Apply the
minimal-delta / zero-staleness contract from SKILL.md.
