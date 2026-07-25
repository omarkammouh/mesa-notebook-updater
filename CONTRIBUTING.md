# Contributing

This repository is one skill. `SKILL.md` and the two directories next to it are
the skill; everything else is scaffolding for testing and packaging it.

Extending the skill is mostly data, not code. When Mesa ships a release, or you
find an API the skill doesn't know about, you add a few facts to the reference
files. The scripts are generic and usually don't change.

## Architecture

```
SKILL.md                 the workflow the agent follows; read this first
references/
  version-catalog.json   every Mesa release: date, python pin, install string,
                         band, and curated highlights/breaking/deprecations
  api-registry.json      the pattern database (schema v2). Each entry pairs
                         regexes with a lifecycle {introduced, deprecated,
                         superseded, removed}. The scanner computes a status at
                         a target from these; nothing is hard-coded
  version-history.md     the human narrative: per-version changes, the §15b
                         target-conditioned "current-best idiom" band table,
                         and the §15c downgrade table
  notebook-editing.md    mechanics of editing .ipynb safely (ids, outputs, magics)
scripts/                 stdlib-only unless noted; Python 3.9+
  mesa_versions.py       version parsing and status_at() lifecycle math, plus a selftest
  scan_notebook.py       the target-conditioned scanner, and the file-wide rules
                         that a per-line regex cannot express: the ContinuousSpace
                         keep rule, the discrete_space base-class rule,
                         grid-missing-random, and pre3-agentset-clock
  check_text_delta.py    the teaching-text gate (minimal delta, no translation, no residue)
  check_report.py        re-derives the report's facts block from the delivered file
  run_notebook.py        executes a notebook pinned to a Mesa version (needs uv)
  normalize_notebook.py  canonicalizes a notebook via nbformat; with --original it
                         also refuses output left behind by a run that did not finish
  update_catalog.py      refreshes version-catalog.json from PyPI
evals/                   8 fixture notebooks with answer keys; see evals/README.md
tools/                   the three checks CI runs, and the bundle builder
```

Two ideas everything rests on:

- **Working is not updated.** Mesa keeps old APIs running, often with no warning,
  for several releases. A green run proves nothing about currency. The registry
  and the catalog are the authority.
- **Status is a function of the target.** The same API is `not-yet-introduced`,
  `current`, `deprecated`, `legacy` or `removed` depending on `--target`.
  `mesa_versions.status_at(entry, target)` computes it, so there is no
  materialized status to keep in sync.

## What helps most

A new Mesa release shipped. Run `python3 scripts/update_catalog.py`, curate the
new catalog entry, add the version-history section, stamp the registry. Steps
below.

The skill left something stale (a false negative). This is the bug class I care
most about. Include the notebook, or a minimal fixture in the style of
`evals/inputs/`, and the target version.

A false positive, or a wrong replacement at some target. Include the scanner
output line and the Mesa version where you checked the actual behaviour.

A new language for the text checks. `check_text_delta.py` has two word lists
that are easy to extend (see below).

New fixtures. A notebook that runs green on its own era's Mesa, plus a manifest
in `evals/expected/` listing every planted finding. Synthetic content only;
nothing copyrighted, nothing you can't publish under MIT.

## Add a new Mesa release

1. **Refresh the catalog:** `python3 scripts/update_catalog.py` (fetches PyPI;
   `--pypi-json FILE` works offline). It fills the mechanical fields (date,
   `requires_python`, `on_pypi`, `installable`, `yanked`) and prints a "needs
   curation" list. It never overwrites curated fields.
   Also glance at https://github.com/mesa/mesa/tags. A version tagged but never
   uploaded to PyPI — it happens: 2.0.0, 2.0.1, 2.2.5 — is invisible to the PyPI
   fetch and has to go in the `GHOSTS` list at the top of `update_catalog.py`,
   since regeneration preserves only the ghosts listed there.
2. **Curate the release** in `references/version-catalog.json`: `python_pin` (a
   Python the release actually supports), `install` (`mesa[rec]==X.Y.Z` for 3.0+,
   plain `mesa==X.Y.Z` for 2.x), `band`, and the `highlights` / `additions` /
   `breaking` / `deprecations` from the release notes and the migration guide.
   Exactly one release carries "Current stable" in its highlights, so move it.
3. **Append a narrative section** to `references/version-history.md` in the same
   format (added / deprecated / removed, with old→new snippets). If the
   current-best idiom changed, extend the §15b band table with a `since:` stamp.
4. **Stamp the registry** in `references/api-registry.json`; format below.
5. **Move the eval ladder up.** `tools/check_fixtures.py` has a `TARGET_LADDER`
   whose top entry should be the latest stable. It keeps passing against the old
   top after a release, so the upgrade direction quietly stops being tested at the
   version people actually target.
6. **Re-probe the negative facts.** A few entries assert that an API *does not
   exist* and carry `verified_absent_through`. Probe them against the new release
   and either bump that field or convert the entry to a normal `introduced` stamp.

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
                                      //   on or directly above it, else an `uncommented-new-api`
                                      //   judge item surfaces (for didactically-heavy modern APIs
                                      //   a migration INSERTS — create_agents, run_for, ...)
  "verified_absent_through": "3.5.1", // (opt) NEGATIVE-FACT entries only: the API named by
                                      //   this pattern does not exist, and was probed absent
                                      //   through this release. A lifecycle cannot express
                                      //   "never existed", so this is the expiry marker
  "applicable_min": "3.0.0",          // (opt) the entry's CONCERN only exists in [min,max)
  "by_target": [                      // (opt) per-band overrides; first match wins, [min,max)
    {"min": "3.0.0", "max": "3.4.0", "replacement": "...", "note": "...", "status": "..."}
  ]
}
```

A band's explicit `status` is honoured verbatim by the scanner. The one worth
knowing is `"status": "judge"`, which makes a stale-at-this-target prose hit
surface without blocking the zero gate. Use it for prose whose token might belong
to another library (`seed=`, `iterations=`), where a hard `stale-term` would make
"re-scan until zero" unreachable on a legitimate false positive.

Rules of thumb:

- A new deprecation on an existing API is a one-field edit: add `"deprecated": "X.Y.Z"`.
- A new API, so that downgrades and mid-version targets don't overshoot to it, is a
  new entry with `"introduced": "X.Y.Z"` and a `replacement` giving the older,
  target-era form.
- Prefer `judge: true` over a hard status when a pattern is ambiguous, for example a
  name other libraries also use. The scanner over-reports on purpose.
- `mesa_versions.validate_lifecycle` rejects prose in a version field at load time.
  Every stamp must be a real version string (`"3.1"`, `"4.0.0a0"`, …).
- **Prose and comment patterns must be morphological, not exact words.** A
  `kind: "api"` entry matches exact identifiers (`\bBaseScheduler\b`), so a
  misspelled identifier in a *comment* (`# Run with BaseSRcheduler`) slips past it,
  and the text-delta gate is markdown-only — a double blind spot, and the one real
  miss found in the wild. The `stale-term-*` prose twins exist to catch exactly
  this, so pattern them on the distinctive morpheme (`\b\w*chedulers?\b`, not
  `\bschedulers?\b`) and confirm the pattern still spares the surviving concept
  word (`scheduling`, `schedule_event`). Every exact-token `api` entry whose concept
  also appears in prose — schedulers, space classes, `seed=` — wants a `stale-term-*`
  twin with a morpheme pattern.

## Verify a lifecycle stamp empirically

Every stamp in the registry was checked against a real install. Do the same:

```bash
# does create_agents exist at 3.0.3? (expect: no — introduced 3.1)
uv run --python 3.12 --with "mesa[rec]==3.0.3" python -c \
  "import mesa; print(hasattr(type('A',(mesa.Agent,),{}), 'create_agents'))"

# which warning does seed= raise at 3.5.1? (expect: FutureWarning)
uv run --python 3.12 --with "mesa[rec]==3.5.1" python -W always -c \
  "import warnings,mesa; ...  # instantiate a model with seed= and capture warnings"
```

Probe the exact boundary — the release just below your claimed version and the
version itself. Off-by-one stamps cause false `not-yet-introduced` flags on
downgrades.

## Before opening a PR

Run the three checks from the repo root. They need no network:

```bash
python3 tools/validate_skill.py
python3 tools/check_fixtures.py
python3 tools/package_skill.py
```

CI runs exactly these.

To exercise the skill itself, point the scanner at any Mesa notebook or `.py`:

```bash
python3 scripts/mesa_versions.py                            # lifecycle-math selftest
python3 scripts/scan_notebook.py YOUR.ipynb --target 3.5.1  # what needs migrating
python3 scripts/scan_notebook.py YOUR.ipynb --target 3.3.0  # a different target
```

To regression-test the text contract, keep a pristine copy of a notebook, run a
migration, then `python3 scripts/check_text_delta.py ORIGINAL.ipynb MIGRATED.ipynb`
and expect zero hard flags.

If you changed lifecycle stamps or replacements, verify them against a real
install and say in the PR how you checked. Guessed stamps cause wrong findings on
downgrades.

If you changed the SKILL.md workflow or the idiom tables, also run at least one
agent-graded eval from `evals/evals.json` and report the result.

## Localizing the text checks

`check_text_delta.py` carries two language-aware heuristics:

- `LANG_WORDS` — function-word sets for the translation detector. Add your
  language's stopwords to catch a "never translate" violation in it.
- `RESIDUE` — migration-commentary phrases that must never appear ("used to be",
  "voorheen", …). Add your language's equivalents.

Both only surface candidates; the SKILL.md reader gate is the final authority on
voice, so a missing language degrades gracefully.

## Ground rules

- Scripts stay stdlib-only and run on Python 3.9+. Two exceptions: `run_notebook.py`
  needs `uv`, and `normalize_notebook.py` needs `nbformat` (run it as
  `uv run --with nbformat python scripts/normalize_notebook.py …`).
- Keep the reference files consistent with each other. The catalog, the registry
  and version-history must tell the same story, and `python3 scripts/mesa_versions.py`
  should pass before you commit.
- The skill bundle ships no example models. Fixtures live under `evals/`, which is
  excluded from the packaged `.skill`.
- The `.skill` bundle is a build artifact. Don't commit it; CI builds it on every
  push and attaches it to tagged releases.

## Releases

Maintainers: update `CHANGELOG.md` and `.claude-plugin/marketplace.json`'s
`metadata.version`, tag `vX.Y.Z`, push the tag. CI attaches the built `.skill` to
the GitHub release.

## Questions

Open an issue. For "is this notebook migrated correctly" questions, attach the
scanner's `--json` output at your target; that usually settles it.
