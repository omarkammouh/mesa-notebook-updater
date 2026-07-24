# Contributing to mesa-notebook-updater

This skill migrates Python **Mesa** (agent-based-modeling) code and notebooks to
*any* Mesa release — forward (upgrade), backward (downgrade), or to a pinned
mid-version — and updates the teaching text in lockstep. It is **standalone and
model-agnostic**: it ships no example models; give it any Mesa `.ipynb` or `.py`
and it works from its version knowledge alone.

Extending it is mostly **data, not code**. When Mesa ships a release, or you find
an API the skill doesn't know, you add a few facts to the reference files — the
scripts are generic and don't change.

## Architecture (what each file is)

```
SKILL.md                      the workflow the model follows (read first)
references/
  version-catalog.json        every Mesa release: dates, python pin, install string,
                              band, and curated highlights/breaking/deprecations
  api-registry.json           the pattern database (schema v2). Each entry pairs
                              regexes with a LIFECYCLE {introduced, deprecated,
                              superseded, removed}. The scanner COMPUTES a status
                              at a target from these — nothing is hard-coded.
  version-history.md          the human narrative: per-version changes, the §15b
                              target-conditioned "current-best idiom" band table,
                              and the §15c downgrade (right-to-left) table
  notebook-editing.md         mechanics of editing .ipynb safely (ids, outputs, magics)
scripts/                      stdlib-only unless noted; run on Python 3.9+
  mesa_versions.py            version parsing + status_at() lifecycle math (+ selftest)
  scan_notebook.py            the target-conditioned scanner (needs the catalog+registry)
                              (+ three FILE-WIDE rules regex-per-line cannot express:
                               the ContinuousSpace keep rule, the discrete_space base-class
                               rule, and `pre3-agentset-clock` — AgentSet activation with no
                               scheduler at a <3.0 target, which hangs batch_run forever)
  check_text_delta.py         the teaching-text gate (minimal-delta / no-translation / residue)
  run_notebook.py             executes a notebook pinned to a Mesa version (needs uv)
  normalize_notebook.py       canonicalizes a notebook via nbformat (+ --original:
                              the execution-state gate — no aborted-run output ships)
  update_catalog.py           refreshes version-catalog.json from PyPI
```

The two ideas everything rests on:

- **"Working is not updated."** Mesa keeps old APIs running (often without a
  warning) for several releases, so a green run proves nothing about currency.
  The registry + catalog are the authority.
- **Status is a function of the target.** The same API is `not-yet-introduced`,
  `current`, `deprecated`, `legacy`, or `removed` depending on the `--target`.
  `mesa_versions.status_at(entry, target)` computes it; there is no materialized
  status to keep in sync.

## Add a new Mesa release (the common contribution)

1. **Refresh the catalog:** `python3 scripts/update_catalog.py` (fetches PyPI; use
   `--pypi-json FILE` to work offline). It fills mechanical fields (date,
   `requires_python`, `on_pypi`, `installable`, `yanked`) and prints a
   "needs curation" list; it never overwrites your curated fields.
   Also glance at https://github.com/mesa/mesa/tags: a version **tagged but never
   uploaded to PyPI** (it happens — 2.0.0, 2.0.1, 2.2.5) is invisible to the PyPI
   fetch and must be added to the `GHOSTS` list at the top of
   `scripts/update_catalog.py` — regens preserve only the ghosts listed there.
2. **Curate the release** in `references/version-catalog.json`: `python_pin`
   (a Python the release actually supports), `install` (`mesa[rec]==X.Y.Z` for
   3.0+, plain `mesa==X.Y.Z` for 2.x), `band`, and the `highlights` /
   `additions` / `breaking` / `deprecations` from the release notes and the
   migration guide.
3. **Append a narrative section** to `references/version-history.md` in the same
   format (added / deprecated / removed, with old→new snippets). If the
   current-best idiom changed, extend the §15b band table with a `since:` stamp.
4. **Stamp the registry** in `references/api-registry.json` (see below).

## Registry entry format (schema v2)

```jsonc
{
  "id": "model-run-control",          // unique, kebab-case
  "kind": "api",                      // api | prose | install  (default: api)
  "patterns": ["\\.run_for\\("],      // regexes; matched per source line
  "applies_to": "both",               // code | markdown | both
  "introduced":  "3.5.0",             // first release the API EXISTS  (null = always)
  "deprecated":  null,                // release it starts WARNING     (optional)
  "superseded":  null,                // release a better form lands   -> status "legacy"
  "removed":     "4.0.0a0",           // release it ERRORS             (optional)
  "replacement": "for old-API entries: the forward fix. For anachronism entries "
                 "(introduced set): the TARGET-ERA form — the downgrade / don't-overshoot "
                 "work list. May contain {TARGET}.",
  "note":  "free text shown with the finding",
  "judge": true,                      // surface for a human check even when computed 'current'
  "judge_when": "stale",              // (opt) "always" (default) = also surface when the API is
                                      //   current at the target (the entry carries a check worth
                                      //   running on correct code); "stale" = only surface when the
                                      //   lifecycle says stale/not-yet-introduced — use when judge
                                      //   exists purely so an ambiguous pattern (pandas .to_list(),
                                      //   numpy .rng) cannot hard-block the zero gate
  "multiline": true,                  // (opt) also match on a newline-flattened, comment-blanked
                                      //   copy of each code cell — for kwarg patterns whose call
                                      //   can span lines (super().__init__( ... seed= ... ))
  "explain": true,                    // (opt) comment-parity check: when this API is current at
                                      //   the target, every matching code line must have a comment
                                      //   on or directly above it, else a `uncommented-new-api`
                                      //   judge item surfaces (for didactically-heavy modern APIs
                                      //   a migration INSERTS — create_agents, run_for, ...)
  "verified_absent_through": "3.5.1", // (opt) NEGATIVE-FACT entries only: the API named by
                                      //   this pattern does not exist, and was probed absent
                                      //   through this release. A lifecycle cannot express
                                      //   "never existed", so this is the expiry marker —
                                      //   re-probe on every new release and, if the API
                                      //   appears, convert the entry to a normal
                                      //   "introduced" stamp. Nothing enforces it; the
                                      //   maintenance checklist in SKILL.md is the reminder
  "applicable_min": "3.0.0",          // (opt) the entry's CONCERN only exists in [min,max)
  "by_target": [                      // (opt) per-band overrides; first match wins, [min,max)
    {"min": "3.0.0", "max": "3.4.0", "replacement": "...", "note": "...", "status": "..."}
  ]
}
```

A band's explicit `status` is honored **verbatim** by the scanner. The one worth
knowing: `"status": "judge"` makes a stale-at-this-target prose hit surface
*without* blocking the zero gate — use it for prose whose token might belong to
another library (`seed=`, `iterations=`), where a hard `stale-term` would make
"re-scan until zero" unreachable on a legitimate false positive.

Rules of thumb:
- A **new deprecation** on an existing API is a one-field edit: add `"deprecated": "X.Y.Z"`.
- A **new API** (so downgrades/mid-version don't overshoot to it) is a new entry with
  `"introduced": "X.Y.Z"` and a `replacement` giving the *older* target-era form.
- Prefer `judge: true` over a hard status when a pattern is ambiguous (e.g. a name
  that other libraries also use). The scanner over-reports on purpose.
- `mesa_versions.validate_lifecycle` rejects prose in a version field at load time —
  every stamp must be a real version string (`"3.1"`, `"4.0.0a0"`, …).
- **Prose/comment patterns must be MORPHOLOGICAL, not exact words.** A `kind: "api"`
  entry matches exact identifiers (`\bBaseScheduler\b`); a misspelled identifier in a
  *comment* (e.g. `# Run with BaseSRcheduler`) then slips past it — and the text-delta
  gate is markdown-only, so it's a double blind spot (the one real miss found in the
  wild). The `stale-term-*` prose twins exist to catch exactly this, so pattern them on
  the distinctive *morpheme* (`\b\w*chedulers?\b`, not `\bschedulers?\b`) so typos and
  compounds still surface, while confirming the pattern still spares the surviving
  concept word (`scheduling`, `schedule_event`). Every exact-token `api` entry whose
  concept also appears in prose (schedulers, space classes, `seed=`) wants a
  `stale-term-*` comment/markdown twin with a morpheme pattern.

## Verify a lifecycle stamp empirically (don't guess)

Every stamp in the registry was checked against a real install. Do the same:

```bash
# does create_agents exist at 3.0.3? (expect: no — introduced 3.1)
uv run --python 3.12 --with "mesa[rec]==3.0.3" python -c \
  "import mesa; print(hasattr(type('A',(mesa.Agent,),{}), 'create_agents'))"

# which warning does seed= raise at 3.5.1? (expect: FutureWarning)
uv run --python 3.12 --with "mesa[rec]==3.5.1" python -W always -c \
  "import warnings,mesa; ...  # instantiate a model with seed= and capture warnings"
```

Probe the exact boundary (the release just below and at your claimed version) —
off-by-one stamps cause false `not-yet-introduced` flags on downgrades.

## Test your change (bring your own model)

The skill ships no fixtures on purpose. To exercise it, point it at any Mesa
notebook or `.py`:

```bash
python3 scripts/mesa_versions.py                              # lifecycle-math selftest
python3 scripts/scan_notebook.py YOUR.ipynb --target 3.5.1   # what needs migrating
python3 scripts/scan_notebook.py YOUR.ipynb --target 3.3.0   # a different target
```

To regression-test the *text* contract, keep a pristine copy of a notebook, run a
migration, then:

```bash
python3 scripts/check_text_delta.py ORIGINAL.ipynb MIGRATED.ipynb   # 0 hard flags expected
```

If you want a graded harness, adopt the eval pattern: an input notebook that runs
green on its own era, plus a `manifest.json` answer key listing the planted
findings and the expected transformation per target. (A companion eval bundle
with worked examples lives outside this package so the skill stays model-free.)

## Localizing the text checks

`check_text_delta.py` carries two language-aware heuristics that are easy to
extend for your community's language(s):

- `LANG_WORDS` — function-word sets for the translation detector. Add your
  language's stopwords to catch a "never translate" violation in it.
- `RESIDUE` — migration-commentary phrases that must never appear ("used to be",
  "voorheen", …). Add your language's equivalents.

Both are heuristics that *surface* candidates; the SKILL.md "reader gate" is the
final authority on voice, so a missing language degrades gracefully.

## Ground rules

- Scripts stay **stdlib-only** (except `run_notebook.py`, which needs `uv`, and
  `normalize_notebook.py`, which needs `nbformat` — run it via `uv run --with nbformat`) and
  run on Python 3.9+ — keep them dependency-free so the skill is portable.
- The skill ships **no models** — keep example notebooks in a separate bundle.
- Every registry stamp is **empirically verified**; note how you checked it.
- Keep the reference files and the narrative in lockstep (catalog ↔ registry ↔
  version-history), and re-run `python3 scripts/mesa_versions.py` before you commit.
