---
name: mesa-notebook-updater
description: >
  Migrate Python Mesa (agent-based modeling) code to any Mesa release — the
  latest by default, or a specific pinned version you name (e.g. "migrate to
  Mesa 3.3.0"), including downgrades (modern code back to an older lab-machine
  version). Especially Jupyter notebooks used for teaching, but also plain .py
  model files. Use this skill whenever the user wants to update, migrate,
  modernize, verify, downgrade, or fix Mesa models or Mesa course/exam
  notebooks; whenever Mesa code fails with errors like "No module named
  'mesa.time'", "RandomActivation", "ModularServer", "unexpected keyword
  argument 'unique_id'"; whenever the user mentions Mesa versions (2.x, 3.x,
  a specific X.Y.Z, SolaraViz, discrete_space), asks "what changed in mesa
  X.Y.Z / which Python does it need", says a Mesa model "still runs but may be
  outdated", or asks to check hand-migrated Mesa code. Ships a complete catalog
  of every Mesa release and a per-version lifecycle of API changes, so it can
  place any model on the timeline and compute what is current, deprecated,
  removed, or not-yet-introduced at ANY target version.
---

# Mesa Notebook Updater

Bring Mesa agent-based models — notebooks first, plus local `.py` modules they
import — to a chosen Mesa release, no matter which Mesa era they were written
for. The target is **whatever version the user names**, or the latest stable if
they don't. Migrations go **up** (old code → newer target) or **down** (modern
code → an older lab-machine target). Edit files **in place**. Verify by scanning
at the target, then executing pinned to the target.

## The two iron rules

**1. Working is not updated — and "updated" is relative to the target.** Mesa
keeps old APIs functional for several releases (often without even a
DeprecationWarning), so a notebook that runs cleanly can still be written
entirely in a dead dialect. Never conclude "nothing to do" from a green run. But
"current" is a function of the **target**: at 3.3 a portrayal dict and
`iterations=` are current; `run_for` and `to_list` don't exist yet. The scanner
computes status at your `--target`; [references/version-history.md](references/version-history.md)
(the ladder + the §15b band table) and [references/version-catalog.json](references/version-catalog.json)
(every release) are the authority on what is current *at that target*. Execution
only proves the migration didn't break anything.

**2. Nothing gets missed.** These are teaching materials; one stale
`RandomActivation` in a comment teaches an API that no longer exists.
Completeness comes from the scanner, not from eyeballing: run
`scripts/scan_notebook.py` (which checks every code *and* markdown cell against
[references/api-registry.json](references/api-registry.json)), fix every
actionable finding, and re-scan until it reports **zero actionable** (`judge`
items are examined and explained, not auto-fixed — see Step 5). Then do the
semantic pass (below) for staleness no pattern can catch — including, on a
**downgrade**, markdown/comments that describe an API newer than the target
(the anachronism entries scan prose too, but the semantic pass is the backstop).

## Workflow

### Step 1 — Establish the target

**If the user named a version** (e.g. "migrate to 3.3.0", "downgrade to the lab's
3.2", "make it run on mesa 3.4.2"), that exact version is the target. **Otherwise**
the target is the latest stable release. Get it from PyPI directly (never from
`uv run --with mesa` or `pip index` — resolution on an incompatible Python or a
cached uv environment silently yields an old version):

```bash
curl -s https://pypi.org/pypi/mesa/json | python3 -c \
  "import json,sys; d=json.load(sys.stdin)['info']; print(d['version'], '| requires python', d['requires_python'])"
```

**Validate the target and read its environment from the catalog**
([references/version-catalog.json](references/version-catalog.json)):

```bash
python3 -c "
import json,sys; sys.path.insert(0,'scripts'); from mesa_versions import parse_version
T=sys.argv[1]; c=json.load(open('references/version-catalog.json'))
rec=next((r for r in c['releases'] if parse_version(r['version'])==parse_version(T)), None)
print(rec if rec else 'UNKNOWN TARGET')
" 3.3.0
```

The record gives `python_pin` and `install` — use them verbatim in every `uv run`
below. Refuse or **confirm with the user first** if the record says: `on_pypi:false`
(a changelog ghost like 2.0.0 — never installable), `installable:false` (0.7.8 has
no files), `prerelease:true` (4.0.0a0 — breaking), or `yanked:true`. If the target
is unknown to the catalog, the scanner (Step 2) errors with the nearest known
versions; if it's genuinely newer than the catalog, extend the catalog first
(see "Maintaining the version history").

The scanner also validates the target itself — passing `--target` a bad version
exits 2 with the nearest known releases, so you never migrate to a version that
doesn't exist.

### Step 2 — Scan at the target and place the model on the timeline

```bash
python3 scripts/scan_notebook.py <notebook.ipynb> --target X.Y.Z   # add --json for machine output
```

`--target` is **required** — every status is computed at that version. The
scanner reports each registry hit with its file location, cell, matched API, the
status **at the target**, and the target-era replacement. It prints a two-sided
era estimate ("written for Mesa ≥ L, < U") and flags a **DOWNGRADE** when the
code's era is newer than the target. Also scan every local `.py` file the
notebook imports (check `import`/`from` statements against files in the
notebook's directory tree).

A finding in a markdown cell or comment is as real as one in code. The scanner
over-reports on purpose (prose words like "schedule" can be innocent) — judge
each hit, but never skip one silently. What each status demands **at the target**:

| Status | Meaning at the target version | Action |
|---|---|---|
| `not-yet-introduced` | the API is **newer** than the target — it won't exist there | rewrite to the target-era form in `replacement` (or delete). Prevents overshoot on mid-target migrations; **this is the downgrade work list** |
| `removed` | errors at import/call time at the target | fix — the notebook cannot run otherwise |
| `deprecated` | runs but warns (FutureWarning) at the target | fix — warnings in teaching material are unfinished migration |
| `legacy` | runs silently at the target, superseded, slated for later removal | migrate to the replacement — **the "working is not updated" case** |
| `install` | pip-install cell | repin to the target with the band-correct extras |
| `stale-term` | prose marker | verify the sentence teaches target behavior; rewrite if not |
| `judge` | pattern is ambiguous | examine the hit; fix or record as false positive |

A status is **suppressed** (not a finding) when the idiom is current *at the
target* — e.g. `RandomActivation` at target 2.4, `iterations=` at target 3.3,
`place_agent` at target 3.1. That suppression is the whole point of target
conditioning; trust it. Use `--show-current` to see suppressed hits as era
evidence when debugging.

One policy exception (encoded in the registry, `judge` so it always surfaces):
legacy `mesa.space.ContinuousSpace` **stays** in every 3.x target — its
replacement is still experimental through 3.5.1. Keep it, ensure no text calls it
current, and report it as a pending Mesa-4 item. The scanner applies this
file-wide: when a file keeps ContinuousSpace and has no legacy *grid* classes,
the space's own API surface (its import, `.pos`, `place_agent`/`move_agent`/
`get_neighbors`) is downgraded from `legacy` to `judge` with a keep-rule note —
those hits are the kept space's API, not unfinished migration. A remaining
legacy grid class disables the downgrade.

### Step 3 — Read the version history and plan

Read [references/version-history.md](references/version-history.md) — the
ordered ladder of Mesa releases and what each changed. Apply every rung between
the model's era and the target **and no rung beyond it**: a migration to 3.3.0
that introduces `rng=`, `to_list()` or `run_for` has *failed* even if it runs,
because those don't exist at 3.3. For a **downgrade** (target older than the
code's era), read the ladder right-to-left and follow §15c. For notebook
mechanics (reading 30 MB files with embedded outputs, editing cells with minimal
diffs, preserving ids and metadata), follow
[references/notebook-editing.md](references/notebook-editing.md).

### Step 4 — Apply edits: code to the target's current-best idiom, text at minimal delta

For **code**, write every Mesa construct the way it would be written *for the
target version* — not merely a form that still runs, and not a form newer than
the target. "It still works" is never a reason to keep a dated idiom *within the
band*; "it's newer/better" is never a reason to overshoot the target. After the
mandatory ladder fixes, walk the **band for your target** in the §15b
target-conditioned modernization checklist and apply every item whose `since ≤
target`; anything not adopted (pedagogy, behavior risk, or newer-than-target) is
named in the report with the reason. "Working is not updated" is a *feature*
choice, not only an error fix: when a newer construct supersedes one that still
runs, adopt it — e.g. on `discrete_space` an immobile agent becomes a
**`FixedAgent`** and a movable one a **`CellAgent`** rather than staying a plain
movable agent (§15b item 11).

Boundaries that keep this safe:

- **Mesa idioms only** — pandas/matplotlib/general Python style is out of
  scope unless broken.
- **Behavior-preserving** — same model logic, parameters, and activation
  semantics. If a modernization changes the *sequence* of random draws (e.g.
  moving per-agent draws into a `create_agents` broadcast), the model is
  statistically equivalent but seeded trajectories may shift — do it, and say
  so in the report.
- **Pedagogy exception** — when a construct is itself the lesson (an explicit
  loop the surrounding text or an exercise walks through), modernize the
  API calls *inside* it but keep the construct; a one-liner that orphans the
  teaching text is a regression, not an upgrade. List these in the report.
- **Stable APIs only** — never move onto experimental modules (that's why
  legacy ContinuousSpace stays).
- **Keep the author's names and cell structure** — modernizing an idiom is not
  a license to rename variables or reorganize the notebook.

For **teaching text** (markdown cells, docstrings, comments) both sides of the
contract are absolute:

- *Minimal delta*: change only the words that describe changed behavior. Do
  not add explanations, do not reword for style or tone, do not translate
  (notebooks may be written in any language, or mix several — leave every
  language exactly as found; never translate).
- *Zero staleness*: after the edit, no sentence anywhere may describe
  previous-version behavior as current. If a paragraph explains how the old
  scheduler works, rewrite that paragraph — in the author's voice — to explain
  the current equivalent in the same number of sentences (±1).
- *No migration residue*: the result must read as if it was originally written
  for the target version. Never add migration commentary anywhere — no
  "updated for Mesa 3.5", no "this used to be RandomActivation" — in code,
  comments, or markdown, and never reword an existing comment to reference
  versions. (Exception: text whose *subject* is version history, like a
  changelog cell the author wrote.)
- *A deprecated kwarg is stale too*: zero-staleness covers not just removed APIs
  but anything that now *warns* — prose telling the reader to pass `seed=`
  becomes `rng=` even though `seed=` still runs, because on the target it is
  deprecated behavior.
- *Tables and structured prose*: migrate a markdown table the same way — keep the
  exact grid (same rows, columns, header count) and hold every cell whose content
  did **not** change **byte-identical**; rewrite only the cells that name a changed
  API (a scheduler-class column → its AgentSet-call equivalent per §4.1), and the
  column header / intro noun if it names the removed concept. Never restructure the
  table or "tidy" the columns. When a removed concept has no one-word replacement
  (e.g. "scheduler" the *category*, vs the object `schedule`), pick a neutral,
  accurate term ("de AgentSet", "activering") and use it consistently — do not
  invent a longer phrase.

### Step 5 — Re-scan until clean, then the semantic pass

Re-run the scanner (same `--target`) until it reports **zero actionable
findings** (`actionable_count: 0` / exit 0). Actionable = removed / deprecated /
legacy / not-yet-introduced / install / stale-term — those must all be fixed.
`judge` items do **not** block zero: a correct `discrete_space` migration always
carries some (e.g. `cell-space-classes` on every `CellAgent`), so the scanner
reports them separately as "judge item(s) to confirm" — examine each and either
fix it or record it as a false positive in the report, but they are not the zero
gate. Then read every markdown cell adjacent to changed code and every docstring
in full, hunting for *semantic* staleness
that no pattern matches — e.g. text saying "the scheduler activates agents in
random order" (no API name, but describes the old mechanism), or a docstring
listing a parameter that no longer exists. Fix under the same contract.

**The text-delta gate (mechanical).** After the semantic pass, diff the prose
against the pre-edit original and let a script catch the contract violations a
human skims past:

```bash
git show HEAD:path/to/notebook.ipynb > /tmp/orig.ipynb   # the pre-edit original
python3 scripts/check_text_delta.py /tmp/orig.ipynb path/to/notebook.ipynb
```

It flags — and these must all be zero — `ADDED-MARKDOWN` (a new explanation; you
may not add prose), `REMOVED-MARKDOWN`/`CELL-COUNT` (structure changed),
`RESIDUE` (a migration-commentary phrase you introduced — "used to be", "voorheen",
"updated for Mesa"), `SENTENCE-DELTA` (a cell whose length moved by >1 sentence —
your rewrite is bigger than the behavior change), and `LANGUAGE-SHIFT` (a
cell whose dominant language flipped — never translate). It then lists every
`CHANGED` cell with its before/after for the **reader gate** below. The scanner
remains the authority on stale API *names* anywhere in the notebook; this script
governs the *delta*.

**The reader gate (voice — "does it read like the author, or like AI?").** For
every `CHANGED` cell the script surfaces, confirm each of these; if any fails,
the edit is too much:

- **Behavior-tied** — the change touches only words describing a Mesa behavior
  that actually changed. If a sentence changed but the behavior it describes did
  not, revert it.
- **Same voice & register** — sentence length, rhythm, formality, and the
  language(s) match the surrounding untouched cells. No added transitions,
  no new hedging.
- **No AI tells** — none of "Note that", "It's worth noting", "Keep in mind",
  "As you can see", "In summary", "Importantly", "simply", "seamlessly", a
  suddenly-tidy bulleted list, or an explanatory clause the author wouldn't have
  written. A migrated cell should be indistinguishable from one the author wrote
  for the target version — not more thorough, not more polished.
- **No teaching added or removed** — same worked examples, same numbers (unless
  a number genuinely shifts with the version — then update just that number and
  say so in the report), same exercise wording.

When in doubt, prefer the smaller edit: the ideal migrated markdown cell is
**byte-identical** to the original, and most cells should be.

### Step 6 — Execute and iterate

Use the `python_pin` and `install` string the catalog gave for the target in
Step 1 (do not hardcode `3.12`/`mesa[rec]` — a 2.x target needs `--python 3.11`
and plain `mesa==X.Y.Z`, since the extras don't exist before 3.0):

```bash
uv run --python <python_pin> --with "<install>" --with nbclient --with ipykernel \
  python scripts/run_notebook.py <notebook.ipynb> --timeout 120
# e.g. target 3.5.1:  --python 3.12 --with "mesa[rec]==3.5.1"
#      target 3.3.0:  --python 3.12 --with "mesa[rec]==3.3.0"
#      target 2.4.0:  --python 3.11 --with "mesa==2.4.0"
```

(`[rec]` = the officially recommended network+viz bundle for 3.0+. A bare `mesa`
install is broken on 3.4+/3.5.x — `import mesa` fails on missing networkx — so
always use the catalog's `install` string. Add `--with seaborn` etc. for
whatever else the notebook imports.)

Executes in place, prints the first failure compactly, and after a green run
lists any warnings (the runner forces hidden DeprecationWarnings visible —
treat every Mesa warning as an unfinished-migration finding). Beware: teaching
notebooks often call `warnings.simplefilter("ignore")` themselves, which
defeats even forced warnings — deprecations then surface *only* through the
scanner. Fix and repeat until green **and** warning-free. Timeouts usually mean an old blocking cell
(e.g. `ModularServer.launch()`); batch-run notebooks may just need a larger
`--timeout`.

**Non-linear or already-broken notebooks.** The runner assumes top-to-bottom
execution (`allow_errors=False`, dies at the first failing cell). Some teaching
artifacts don't satisfy that *for reasons unrelated to Mesa* — a "run the model
cell at the bottom first" note, imports defined near the end, or leftover
references to symbols from an earlier notebook version (`NameError` on an
undefined helper). Confirm it's pre-existing by running the **pristine original**
through the runner: if it fails at the same cell with the same non-Mesa error,
the notebook was never linearly runnable and the failure is not your migration.
In that case: (a) **never report a false green**; (b) validate the *migrated Mesa
path* by extracting the model/def/run cells into a scratch notebook (or a small
harness) and running that pinned to the target — instantiate every migrated model
and step it; (c) in the report, state the pre-existing non-Mesa blocker plainly
and that Mesa correctness was verified by extraction. Do **not** reorder or invent
cells to force a linear run — that violates the structure/minimal-delta contract.

Then close with the **finishing gate** (details in
[references/notebook-editing.md](references/notebook-editing.md)): canonicalize
with `scripts/normalize_notebook.py`, and prove the diff against the pre-edit
original (`git show HEAD:… ` + `nbdiff --ignore-outputs`) — every hunk must map
to a migration finding or a modernization-checklist item, every fixed finding
must appear, and markdown hunks must satisfy the minimal-delta text contract
(run `scripts/check_text_delta.py` against the same pre-edit original — zero hard
flags — and clear its reader-gate `CHANGED` list, per Step 5).

### Step 7 — Report

Per notebook: the target version and the band applied; which Mesa era the model
was; what changed grouped by theme (APIs, teaching text, installs); any
behavioral differences (activation order, seeding — numeric results may shift);
a **"deliberately not applied (newer than target)"** list naming the rungs above
the target (e.g. targeting 3.3: "3.4 iterations→rng, 3.5 seed→rng/run_for/to_list
not applied") so a future upgrade has a ready work list; and — if the user's own
kernel environment runs a different Mesa — the exact install command for it.

**Declared-Python consistency (a gate blind spot).** Neither the scanner nor
`check_text_delta` inspects the notebook's `metadata` (`kernelspec`,
`language_info.version`) — only cells. When a notebook *states* its Python or Mesa
version, keep every statement consistent with the target: the env-note markdown,
any "Python 3.x / Mesa X.Y.Z" banner, **and** the `kernelspec.display_name` /
`language_info.version` metadata (the target's Python floor comes from the
catalog's `python_pin`/`requires_python`). Update the metadata only to a version
the target actually supports; don't fabricate a patch number you didn't run on.
If you leave metadata as-is, say so in the report — a notebook migrated to a
target that needs Python 3.12 should not still advertise Python 3.11.

## Downgrades (target older than the code's era)

When the scanner prints **DOWNGRADE**, the work list is the `not-yet-introduced`
findings — every API newer than the target, rewritten to the target-era form in
each finding's `replacement`. Follow §15c of version-history.md for the
right-to-left mapping and the honesty caveats it requires in the report:

- `model.rng` / numpy draws have **no clean pre-3.0 reversal** — moving them to
  `self.random` changes the draw sequence; seeded results shift. Say so per finding.
- `create_agents` → explicit loop reorders draws (statistically equivalent).
- SolaraViz → ModularServer (only for 2.x targets) is a rewrite, not a mapping —
  flag it as the largest chunk.
- Behavior-preservation is weaker downhill — always execute on the pinned target
  and report seed-trajectory shifts.
- Never move code *onto* an experimental module to satisfy a downgrade (targeting
  3.1 keeps `mesa.space`; it does not adopt `experimental.cell_space`).

## Answering version questions (no migration)

The catalog answers "what changed in 3.1.3?", "which Python does 2.3.4 vs 3.4.0
need?", "can I target 0.7.8 / 2.0.0?" directly — read
`references/version-catalog.json` (`highlights`/`additions`/`breaking`,
`requires_python`/`python_pin`, `on_pypi`/`installable`) and version-history.md
for the narrative. 0.7.8 has no files (uninstallable); 2.0.0 is a changelog ghost
never on PyPI.

## Maintaining the version history

This skill is meant to be extended by the community — see
[CONTRIBUTING.md](CONTRIBUTING.md) for the registry schema, how to add a Mesa
release, how to verify a lifecycle stamp empirically, and how to localize the
text checks. The short version: when Mesa releases a new version, extend the
skill instead of rediscovering everything (both machine files stay in lockstep
with the narrative):

1. **Catalog:** run `python3 scripts/update_catalog.py` (fetches PyPI; add
   `--pypi-json FILE` to work offline). It refreshes mechanical fields for every
   release, preserves your curated fields, and prints a "needs curation" list.
2. **Curate** the new release in `references/version-catalog.json`: `python_pin`,
   `install`, `band`, and the `highlights`/`breaking`/`deprecations`/`additions`
   from the release notes (`https://github.com/mesa/mesa/releases`) and migration
   guide (`https://mesa.readthedocs.io/latest/migration_guide.html`).
3. **Narrative:** append a section to `references/version-history.md` — same
   format (added / deprecated / removed with old→new snippets) — and, if the
   current-best idiom changed, extend/add a §15b band with `since:` stamps.
4. **Registry lifecycle stamps:** in `references/api-registry.json`, a new
   deprecation is a one-field edit (`"deprecated": "3.6.0"`) on the existing
   entry; a new API is a new anachronism entry with `"introduced": "3.6.0"` and
   a target-era `replacement`. Empirically confirm uncertain stamps with a quick
   pinned probe (`uv run --python P --with "mesa==V" python -c "..."`) — every
   stamp already in the registry was verified this way.
5. Re-run Steps 2–7 on each Mesa model/notebook to roll it forward.

## Hard rules

- **In place, no backups** — the user's files are under their own version control.
- **The target is explicit** — user-named version, else latest. The `--target`,
  the Python pin, and the install string come from the catalog, never from memory.
- **Nothing newer than the target** — `not-yet-introduced` findings are as
  mandatory as `removed` ones. A 3.3 migration that emits `run_for`/`to_list`/`rng=`
  has failed. Apply every rung up to the target and no rung beyond it.
- **Registry findings are never skipped silently** — each is fixed or explicitly
  judged a false positive in the report.
- **Green run proves nothing about currency** — only the scanner (at the target)
  + history/catalog do.
- **Code is written in the target's idiom** — after correctness fixes, apply the
  §15b band for the target; "still works" never justifies a dated form *within
  the band*, and "it's newer" never justifies overshooting the target (and never
  experimental APIs, and never at the cost of the lesson).
- **Teaching text: minimal delta, zero staleness** — both, always. "Current"
  means current at the target.
- **Pinned installs**: a `pip install mesa==old` cell becomes the target pin with
  the band-correct extras (`mesa[rec]==V` for 3.0+, plain `mesa==V` for 2.x); keep
  it commented if it was commented.
