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
  outdated", or asks to check hand-migrated Mesa code. Also use whenever the
  file in question imports mesa or subclasses mesa.Model/mesa.Agent, even if
  the user never says "Mesa" — "this notebook is old", "make my model work
  again", "prepare the course notebooks for next year", "check of dit notebook
  nog klopt". More trigger errors: "Agent.__init__() takes 2 positional
  arguments but 3 were given", "'Model' object has no attribute 'schedule'",
  "cannot import name 'PropertyLayer'"; also when Mesa code merely WARNS
  (DeprecationWarning/FutureWarning about seed=, iterations=) or misbehaves
  silently after an update (empty grid, cell.agents empty, agents never find
  neighbors). Ships a complete catalog of every Mesa release and a per-version
  lifecycle of API changes, so it can place any model on the timeline and
  compute what is current, deprecated, removed, or not-yet-introduced at ANY
  target version.
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

## Objectives — what "done" means, measurably

Every migration is scored against these eight objectives; each maps to a
mechanical check. The report's digest states any objective not met and why.

| # | Objective | Measured by |
|---|---|---|
| O1 | **Current at the target**: zero actionable findings | `scan_notebook.py --target` exit 0 / `actionable_count: 0`, incl. the finishing-gate rescan |
| O2 | **Runs at the target**: pinned execution green with zero Mesa warnings | `run_notebook.py` under the catalog pin (or the documented extraction path for never-linear notebooks) |
| O3 | **Nothing newer than the target**: zero `not-yet-introduced` | subset of O1, reported separately (the overshoot/downgrade guard) |
| O4 | **Text contract held**: zero hard text-delta flags; every changed prose/comment cell passes the reader gate; every model↔Mesa *claim* (compatibility/support/tested-range/version) is true of the delivered file, not just number-matched | `check_text_delta.py --target` exit 0 + reader-gate walk of `CHANGED`/`CHANGED-COMMENTS` + `compat-support-claim` judge items dispositioned (Step 5 claim pass) |
| O5 | **Judge discipline**: every judge finding dispositioned (fixed / false positive + why / correctly-silent) | Step 7 item 4 count == scanner `judge_count` |
| O6 | **Structure preserved**: same cells, same ids, no added/removed markdown | `CELL-COUNT`/`ADDED-*`/`REMOVED-*` all absent |
| O7 | **Report complete and true**: all 8 Step-7 items present, digest last, and the facts block carries every fact the file can settle | checklist self-audit + `check_report.py` exit 0 (zero DISAGREE) |
| O8 | **Declared versions consistent**: kernelspec/`language_info`/version banners match the target, or the exception is named in the report | Step 5 metadata pass + report item 7 |

## Workflow

**Paths:** every `scripts/...` and `references/...` in this file is relative to
THIS SKILL'S directory — invoke scripts by **absolute path** and keep your cwd
in the user's project (the scripts resolve their own data files internally; a
relative invocation from the project dir is the classic FileNotFoundError).
Never fall back to ad-hoc grep "scanning" if an invocation fails — fix the path.

**Plain `.py` inputs:** the scanner and `check_text_delta.py` accept `.py`
files unchanged (a .py is one code cell). Differences: execution (Step 6) uses
a pinned import-instantiate-step harness instead of `run_notebook.py`
(`uv run --python <pin> --with "<install>" python -c "import model; m = model.MyModel(...); [m.step() for _ in range(20)]"`),
`normalize_notebook.py` does not apply, and the diff proof is plain `git diff`.

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
python3 scripts/scan_notebook.py <notebook.ipynb> [helper.py ...] --target X.Y.Z   # add --json for machine output
```

The scanner accepts multiple files — pass the notebook **plus every local
`.py` it imports** (check `import`/`from` statements against files in the
notebook's directory tree) in one invocation, so era and ladder are computed
over the whole model.

`--target` is **required** — every status is computed at that version. The
scanner reports each registry hit with its file location, cell, matched API, the
status **at the target**, and the target-era replacement. It prints a two-sided
era estimate ("written for Mesa ≥ L, < U") and flags a **DOWNGRADE** when the
code's era is newer than the target. It also prints the **migration ladder** —
for the APIs actually matched in these files, every lifecycle rung the migration
must act on, version by version (e.g. "3.0.0 deprecated scheduler-classes →
AgentSet…; 3.1.0 removed …; 3.5.0 deprecated model-seed-kwarg → rng=…"), each
with the replacement in its **target-era form**. That ladder is the
deprecation-focus summary: what became deprecated/removed between the model's
era and the target, and what each thing becomes *at this target* (in `--json`:
the `ladder` array). Also scan every local `.py` file the
notebook imports (check `import`/`from` statements against files in the
notebook's directory tree).

The scanner also reports **code cells that are not valid Python** (in `--json`:
`non_python_code_cells`). Teaching notebooks often hold prose or ASCII-art
pattern diagrams (`. # # .`) in a *code* cell — the author meant markdown. Any
linear execution dies there with a `SyntaxError` that has nothing to do with
Mesa, so knowing it up front saves a whole pinned install-and-run cycle: plan
for the **extraction path** in Step 6 from the start. Never convert, reorder or
delete these cells — that violates the structure contract; report them as a
pre-existing condition.

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

A third file-wide rule guards **downgrades below 3.0**: the AgentSet surface
exists from 2.4, so `agents.shuffle_do("step")` activation *looks* portable down
to 2.4 — but below 3.0 the AgentSet does not drive the clock. `model.steps`
doesn't exist there (2.x has only the private `_steps`), and `batch_run` loops
`while model.running and model._steps <= max_steps`, which only a scheduler
advances. A downgraded model that keeps AgentSet activation with no scheduler
scans clean and then **hangs forever** in every `batch_run` cell — no exception,
100% CPU (verified on 2.4.0). The remedy is always the same: put back
`RandomActivation` + `schedule.add` + `schedule.step()` and map `model.steps` →
`schedule.steps`, per §15c. Nothing per-line can see an *absent* scheduler,
which is why this is file-wide.

What counts as "a scheduler is present" is deliberately strict, because each
loose reading is a way to ship a hanging notebook:

- the scheduler must be **constructed** (`RandomActivation(self)`), not merely
  named — a docstring or comment narrating the migration ("moved away from
  `RandomActivation`") is not a scheduler;
- it must be **driven** — some `schedule.step()` must actually be called. A
  scheduler that is bound and never stepped advances `_steps` exactly as little
  as no scheduler at all;
- string literals are blanked before this check (only here — everywhere else a
  dead API name inside a docstring is a real finding).

Both activation forms count as AgentSet activation: `agents.shuffle_do("step")`
and the multi-type `agents_by_type[T].shuffle_do("step")`.

The scanner emits, both actionable:

| finding | when | why it matters |
|---|---|---|
| `pre3-agentset-clock` | sub-3.0 target, AgentSet activation, no scheduler *driving* the clock | `batch_run` hangs forever, silently |
| `pre3-scheduler-unpopulated` | a scheduler is constructed and stepped, but nothing is ever `add`ed to it | the clock advances, so it does not hang — every step just activates zero agents and the run yields flat, empty results |

A second file-wide rule guards the cell-space migration itself: in any file that
uses `mesa.discrete_space` (targets ≥ 3.2), every plain `class X(Agent)` is
flagged — **actionable** when its body references `self.cell` (it plainly lives
on the cell space), `judge` otherwise (a genuinely non-spatial agent correctly
stays `mesa.Agent`). This exists because the failure is **silent**: a plain
`Agent` assigned `agent.cell = grid[...]` constructs without error but registers
on *no* cell — `cell.agents` stays empty and every neighbor mechanic quietly
returns nothing (verified on 3.5.1). A green run does not expose it.

### Step 3 — Read the version history and plan

Open [references/version-history.md](references/version-history.md) and read,
at minimum: the sections the scanner's ladder pointed at, **the §15b band row
for your target** (this is mandatory — Step 7 makes you enumerate it), and
**§15c if the scanner said DOWNGRADE**; pull other sections on demand. Apply
every rung between the model's era and the target **and no rung beyond it**: a
migration to 3.3.0 that emits `to_list()` or `run_for` has *failed* even if it
runs — those don't exist at 3.3 (AttributeError) — and one that emits `rng=`
has overshot the band (`rng=` exists since 3.0 but is the 3.4+ idiom; at ≤3.3
`seed=` is current-best). For notebook
mechanics (reading 30 MB files with embedded outputs, editing cells with minimal
diffs, preserving ids and metadata), follow
[references/notebook-editing.md](references/notebook-editing.md).

### Step 4 — Apply edits: code to the target's current-best idiom, text at minimal delta

**STOP — recoverability gate (before the FIRST edit).** Steps 5–6 diff against
the pre-edit original, and edits are in-place. Confirm the original is
recoverable: `git rev-parse HEAD` succeeds AND the file is tracked and clean
(`git status --short <file>` empty). If either fails (no commits yet, untracked
file, dirty tree), snapshot the pristine file to the session scratchpad NOW and
use that snapshot wherever these steps say `git show HEAD:…`. The "no backups"
hard rule forbids clutter in the *user's* tree, not a scratch copy — without
one, every text gate silently dies.

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

For **teaching text in markdown cells** both sides of the contract are
absolute (comments and docstrings follow the *comment-parity* rule below
instead, because they must track code that the migration itself changes):

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

**Comments and docstrings follow the code (comment parity).** A comment's job
is to explain the line it sits on — and the migration changes those lines, so
comments cannot be frozen the way markdown is. The notebook's own commenting
style (density, language, voice) is the norm; against it, per case:

- **Replace** — the code under a comment was rewritten and the comment
  describes the old construct ("# add agent to the scheduler" above a
  `shuffle_do` line): rewrite the comment to describe the new construct, same
  length class, same language.
- **Extend** — the old comment is still true but the migrated line now does
  something more it doesn't cover (a `create_agents` broadcast that also
  assigns attributes): extend it minimally rather than replacing.
- **Add** — the migration **inserted a construct that is new at the target**
  (`rng=`, `run_for`, `SpaceRenderer`, `FixedAgent`, `create_agents`, ...) with
  no comment on or above it. The pre-migration comments cannot explain it —
  they were written before it existed. If the notebook's style comments
  comparable steps, add a short comment saying **what the line does** (never
  that it is new, never a version number — the residue rule is absolute).
  The scanner surfaces every candidate as an `uncommented-new-api` judge item
  (registry entries flagged `explain:true`); each is either commented or
  recorded as correctly-silent (sparse notebook, or the markdown cell above
  already explains it).
- **Remove** — the construct a comment described was deleted outright (an
  orphaned "# create the scheduler" with no successor line, a comment for a
  dropped `next_id()` call): remove the comment with its code. Never leave a
  comment pointing at nothing.
- **Untouched code keeps untouched comments** — parity cuts both ways; no
  drive-by rewording.

Docstrings: same parity — a parameter list must match the migrated signature
(`seed` renamed to `rng` in the docstring too); remove documented parameters
that no longer exist; add one line for a parameter the migration introduced.
Every comment/docstring edit surfaces in `check_text_delta` as
`CHANGED-COMMENTS` for the reader gate, and an added comment in the wrong
language is a hard `LANGUAGE-SHIFT` flag.

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
Sweep `#` comments with the same eye as markdown — comment prose goes stale
the same way — and close the **comment-parity loop** (Step 4): work through
every `uncommented-new-api` judge item (comment it or record it as
correctly-silent), confirm every rewritten line's comment describes the *new*
construct, and delete orphaned comments whose code is gone. The
concept-vs-token rubric for any prose hit: **edit** when the
text names a dead API token/kwarg or instructs something that now warns or
errors at the target ("pass `seed=`", "the scheduler object", "`MultiGrid`");
**keep** when only the surviving concept is described ("a random seed", "N
iterations/replications", "simultaneous activation" as a regime name).

**The claim-verification pass (part of the semantic pass, easy to skip).** The
rubric above governs prose that names an *API*. A second class of prose names
no API and carries no wrong number after you fix the banner, yet is still made
false by the migration: **factual claims about the model↔Mesa relationship** —
"up-to-date with mesa X", "compatible with newer versions", "tested up to Y",
"not all features of newer versions are supported", "this model requires mesa
Z", "feature F is not supported". These are *claims about the delivered work*,
not descriptions of a mechanism, and they are the one place a migration can
ship a lie while every mechanical net stays green: `stale-version-claim` only
checks the version *number*, `check_text_delta` only flags a stale API *name*,
and neither can read a sentence's truth value. So for every such sentence
(the scanner surfaces the common phrasings as `compat-support-claim` judge
items — work that list, then sweep for phrasings it missed), **verify the
claim against what you actually delivered**, and treat a version banner as a
claim, not a digit:

- A two-tier banner — "up-to-date with 3.0.3" + "tested up to 3.2.0, not all
  newer features supported" — does **not** migrate by bumping both numbers to
  the target. That collapses it into "up-to-date with T / tested up to T /
  newer features unsupported", which is vacuous (nothing newer than T was
  tested) *and* false (after a full migration the model **is** the target's
  current-best form, so it does not lack the target's features). The honest
  result is the bare "up-to-date with mesa T"; delete the forward-compat hedge —
  you tested on T, not beyond it, so you cannot assert anything about newer
  releases, and the "not all features supported" caveat is no longer true.
- Keep a claim only to the extent the delivered migration backs it. "Requires
  mesa T" is fine if T is the pin; "supports SolaraViz" is fine only if the
  notebook still does. When in doubt, state less.

Record every `compat-support-claim` disposition in the report's judge log
(Step 7 item 4), same as any other judge finding.

**The text-delta gate (mechanical).** After the semantic pass, diff the prose
against the pre-edit original and let a script catch the contract violations a
human skims past:

```bash
git show HEAD:path/to/notebook.ipynb > /tmp/orig.ipynb   # or the Step-4 scratchpad snapshot
python3 scripts/check_text_delta.py /tmp/orig.ipynb path/to/notebook.ipynb --target X.Y.Z
```

(`--target` is the same version as the scan — without it the staleness check
falls back to stamp-matching and false-flags prose that is current at your
target.) It flags — and these must all be zero — `ADDED-MARKDOWN` (a new
explanation; you may not add prose), `REMOVED-MARKDOWN`/`CELL-COUNT` (structure
changed), `RESIDUE` (a migration-commentary phrase you introduced — "used to
be", "voorheen", "updated for Mesa"), `RESIDUAL-STALE` (an API name that is
stale *at the target* still sits in changed prose), `SENTENCE-DELTA` (a cell
whose length moved by >1 sentence — your rewrite is bigger than the behavior
change), and `LANGUAGE-SHIFT` (a cell whose dominant language flipped, or an
added comment in a language other than the notebook's comments — never
translate). It then lists every `CHANGED` and `CHANGED-COMMENTS` cell with
before/after for the **reader gate** below. The scanner
remains the authority on stale API *names* anywhere in the notebook; this script
governs the *delta*.

**Declared-Python/Mesa metadata is edited HERE (not in the report).** When the
notebook states its Python or Mesa version anywhere — an env-note markdown
cell, a "Python 3.x / Mesa X.Y.Z" banner, or the `kernelspec.display_name` /
`language_info.version` metadata — make every statement consistent with the
target now (Python floor from the catalog's `python_pin`/`requires_python`;
neither the scanner nor check_text_delta sees notebook `metadata`, only cells).
Update metadata only to a version the target actually supports; don't fabricate
a patch number you didn't run on. If you deliberately leave metadata as-is,
you must say so in the report.

**The reader gate (voice — "does it read like the author, or like AI?").** For
every `CHANGED` cell **and every `CHANGED-COMMENTS` cell** the script surfaces,
confirm each of these; if any fails, the edit is too much:

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
- **Claims are true, not just number-matched** — for any sentence asserting what
  the model supports / is compatible with / was tested on / requires (the Step-5
  claim pass, `compat-support-claim`), confirm it holds for the *delivered* file.
  Bumping the version number inside a compatibility hedge is not a fix; a
  now-false "not all newer features supported" must be corrected or deleted, and
  minimal-delta permits the deletion because the migration changed the fact.

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

**Non-Mesa breakage you will meet (don't rediscover it).** Two recurring
classes, both out of scope except where they *block* the green run — fix the
minimum and report it separately as non-Mesa:

- *Plotting-library drift.* Recent matplotlib/seaborn releases broke calls that
  Mesa-era teaching notebooks are full of: `boxplot(labels=)` → `tick_labels=`,
  seaborn `FacetGrid.add_legend(handles=[...])` → `legend_data={...}`, and
  `vert=` → `orientation=` (a warning only, leave it).
- *Non-Python code cells* — the scanner already listed them in Step 2; they are
  the usual reason a linear run cannot be reached at all.

**Non-linear or already-broken notebooks.** The runner assumes top-to-bottom
execution (`allow_errors=False`, dies at the first failing cell). Some teaching
artifacts don't satisfy that *for reasons unrelated to Mesa* — a code cell that
isn't Python (above), a "run the model cell at the bottom first" note, imports
defined near the end, or leftover
references to symbols from an earlier notebook version (`NameError` on an
undefined helper). Confirm it's pre-existing by running the **pristine original**
through the runner: if it fails at the same cell with the same non-Mesa error,
the notebook was never linearly runnable and the failure is not your migration.
Run that pristine-original check pinned to the notebook's **own era** (the
scanner's lower bound L, via the catalog's install string for L) — running an
old-era original at the *target* dies earlier, at a Mesa cell, with a different
error, and proves nothing about pre-existence.
In that case: (a) **never report a false green**; (b) validate the *migrated Mesa
path* by extracting the model/def/run cells into a scratch notebook (or a small
harness) and running that pinned to the target — instantiate every migrated model
and step it; (c) in the report, state the pre-existing non-Mesa blocker plainly
and that Mesa correctness was verified by extraction. Do **not** reorder or invent
cells to force a linear run — that violates the structure/minimal-delta contract.
One more staleness surface on this path: a linear green run rewrites every cell's
**outputs**, but extraction leaves the original outputs untouched — if an
unexecuted cell's stored output shows a dead API (an old DeprecationWarning, the
repr of a removed class), students will read it as current. Clear or regenerate
such outputs, or name them in the report.
The mirror case is contamination rather than staleness, and it is not optional:
the aborted linear run that sent you down this path *wrote to the file* before it
died — an `execution_count` on the cells it reached and, on the failing one, a
stored traceback. A delivered notebook must **never** carry output produced by a
run that did not complete; a student opening it reads that `NameError` as the
notebook's own result. Restore every such cell to the **pre-edit original's**
`execution_count`/`outputs` — on this path the original's outputs are the only
correct ones, since no complete run at the target ever regenerated them. The
finishing gate's check 1 detects this mechanically.

Then close with the **finishing gate** — five numbered checks, in order
(details in [references/notebook-editing.md](references/notebook-editing.md));
check 5 needs the Step-7 report, so it closes the loop after you write it:

1. **Normalize**: canonicalize with `scripts/normalize_notebook.py --original
   <orig>` (skip for `.py` inputs) — the round-trip, plus an execution-state
   audit against the pre-edit original: `ERROR-OUTPUT` (a stored traceback the
   original did not have) and `PARTIAL-RUN` (an `execution_count` written by a
   run that left other cells unexecuted) both exit 4. A cell that teaches an
   error on purpose carries it in the original too and stays silent; so does a
   complete linear run, which numbers every cell.
2. **Final scan**: rerun `scripts/scan_notebook.py --target X.Y.Z` — still
   **zero actionable**. (Warning-chasing edits made during Step 6 have never
   been scanned; this catches an overshoot pasted in after Step 5.)
3. **Diff proof**: against the pre-edit original (`git show HEAD:…` or the
   Step-4 snapshot) via `nbdiff --ignore-outputs` (plain `git diff` for `.py`)
   — every hunk maps to a migration finding or a named §15b item; every fixed
   finding appears.
4. **Text gate**: `scripts/check_text_delta.py <orig> <migrated> --target X.Y.Z`
   — zero hard flags — and clear its reader-gate `CHANGED`/`CHANGED-COMMENTS`
   list, per Step 5.
5. **Report gate** (after Step 7 is written): `scripts/check_report.py
   <report.md> <migrated> --original <orig> --target X.Y.Z` — **zero
   DISAGREE**. It ignores your prose entirely and re-derives every line of the
   report's `mesa-report-facts` block (Step 7) from the delivered file: the
   execution mode and warning count against the stored outputs, the output/
   error cells against the cells, the metadata values against `metadata`, the
   counts against the scanner, and each `output_quote` against the stored
   output that must contain it. Each DISAGREE is a claim the artifact
   contradicts — fix the file or fix the block, never leave both. Fields the
   file cannot settle (`cells_before` without `--original`, an extraction-mode
   run) come back `unverifiable`, which is not a failure; the digest cap is an
   advisory. A missing or malformed block exits 2 — the block is the claim of
   record, so a report without one cannot pass.

### Step 7 — Report

Per notebook, a checklist — every item present, "none" written out when empty
(these collect the debts declared in Steps 2–6; a missing item means the step
that generates it was skipped). Write every claim from the **delivered file**,
not from what the migration meant to do — read the value back before stating it
— then run the finishing gate's check 5 on the finished report:

1. **Target + band + era**: the target version, the §15b band applied, the
   scanner's era bracket for the model.
2. **Deprecation/replacement table** — one row per changed construct: old form
   | version that deprecated/removed it (from the finding's lifecycle stamps /
   the scanner's ladder) | target-era form it became.
3. **§15b band enumeration** — EVERY item of the band row, each marked
   `applied` / `n-a` (not present in this model) / `not adopted + reason`
   (pedagogy, behavior risk, newer-than-target). Unfakeable without reading
   the band; "not adopted" without a reason is a fail.
4. **Judge log** — every `judge` finding (incl. `uncommented-new-api` and the
   ContinuousSpace keep-rule items) with its disposition: fixed / false
   positive + why / correctly-silent.
5. **Behavioral differences**: activation order, RNG draw-order shifts,
   seeded-trajectory changes — numeric results may shift; say where and why.
6. **Deliberately not applied (newer than target)**: the rungs above the
   target (e.g. targeting 3.3: "3.4 iterations→rng, 3.5 seed→rng/run_for/
   to_list not applied") — a future upgrade's ready work list.
7. **Execution + environment**: green-run status and remaining warnings
   (Step 6); on the extraction path, the pre-existing non-Mesa blocker and any
   stale outputs left in unexecuted cells; what was done about
   kernelspec/`language_info` metadata (edited in Step 5 — or why left as-is);
   and — if the user's own kernel runs a different Mesa — the exact install
   command for it.
8. **Digest (always last, always present).** Close the report with a
   swallowable per-notebook summary the user can absorb in seconds — a handful
   of ultra-compact lines, no filler, technical terms exact:

   ```
   WolfSheep — 3.2-era → 3.5.1. 7 fixes: seed=→rng= (4 sites), MultiGrid→
   OrthogonalMooreGrid, scheduler table rewritten, install repinned.
   Run: green, 0 warnings. Seeded trajectories shift (rng change). 2 judge
   items = false positives. Nothing pending.
   ```

   One block per notebook; batch runs end with one extra line totalling
   notebooks/fixes/greens. Items 1–7 are the audit trail; the digest is what
   the user actually reads — never skip it, never let it exceed ~6 lines.

**The facts block — required, one per report, immediately before the digest.**
This block is the claim of record, and check 5 re-derives every line of it from
the delivered file. Read each value out of the file (and out of the final scan)
as you write it; state nothing here you have not read back. `n-a` is only for
the notebook-only fields on a `.py` input.

Placement is part of the contract, and check 5 fails closed on all three points:

- **One block, counting every fence form.** A ` ``` `, `~~~` or 4-backtick
  block named `mesa-report-facts` is a claim block. Two of them — even "a decoy
  plus the real one" — is an error, not a pick-the-good-one situation.
- **Plainly visible.** A claim block inside an `<!-- -->` HTML comment is not a
  claim anyone reads; it is an error.
- **Immediately before the digest**, with only blank lines and headings in the
  gap. The digest must be the report's last fenced block.

Check 5 verifies the block, not the prose — that is why the block must sit where
the reader sees it beside the digest. Any number stated in the prose or the
digest must be copied from the block, never written from intent: nothing checks
the prose.

```mesa-report-facts
target: 3.5.1                     # the migration target
file: nb_21e4.ipynb               # basename of the delivered file
execution: linear-green           # linear-green | extraction | blocked
warnings_in_outputs: 0            # Future/Deprecation/UserWarnings in stored outputs,
                                  # subclasses too (MatplotlibDeprecationWarning counts);
                                  # a total — say in item 7 which of them are Mesa's
error_outputs: none               # none, or the cells storing an error output
output_cells: 1,3,5,7             # none, or the cells with outputs/execution_count
outputs: regenerated              # cleared | regenerated | preserved | mixed
actionable_count: 0               # final scan at the target (O1)
judge_count: 5                    # final scan at the target (O5)
language_info.version: 3.12.12    # notebook metadata, or `absent`
kernelspec.name: python3
kernelspec.display_name: Python 3
widgets_metadata: absent          # absent | present:N
cells_before: 8
cells_after: 8
# one output_quote line per run number the report quotes (no trailing comment —
# this value is matched verbatim against the stored output)
output_quote: Occupied cells: 18
```

Every number the report presents as a **run result** — a printed count, a sweep
row, a final tally — gets an `output_quote:` line carrying the literal the
notebook stored (whitespace is normalized before matching). A number produced by
an extraction harness with no stored output has no quote line and stays a prose
claim the reader gate judges.

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
never on PyPI; 2.0.1 and 2.2.5 exist only as git tags (never released) — none of
these are valid targets, and the catalog says so per version.

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
5. **Re-probe the negative facts.** A handful of entries assert that an API
   *does not exist* (`model-remove-agent`), which no lifecycle stamp can
   express and no release note will correct. Each carries
   `verified_absent_through`; probe them against the new release and either
   bump that field or, if the API has appeared, convert the entry to a normal
   `introduced` stamp. Nothing fails when this is skipped — that is exactly why
   it is a checklist item.
6. **Move the eval ladder up.** `tools/check_fixtures.py` scans every fixture at
   a fixed `TARGET_LADDER` whose top entry is meant to be the latest stable.
   It keeps passing against the old top after a release, so the upgrade
   direction quietly stops being tested at the version people actually target —
   bump the top entry and re-run `python3 tools/check_fixtures.py`.
7. **Refresh what claims to be current.** `version-catalog.json` calls exactly
   one release "Current stable" in its `highlights`, and `update_catalog.py`
   preserves curated fields, so the old one keeps the label unless you move it.
   Same for §0 of version-history.md.
8. Re-run Steps 2–7 on each Mesa model/notebook to roll it forward.

## Hard rules

- **In place, no backups** — the user's files are under their own version control.
- **The target is explicit** — user-named version, else latest. The `--target`,
  the Python pin, and the install string come from the catalog, never from memory.
- **Nothing newer than the target** — `not-yet-introduced` findings are as
  mandatory as `removed` ones. A 3.3 migration that emits `run_for`/`to_list`
  has failed (they don't exist there); one that emits `rng=` has overshot the
  band (it exists since 3.0, but `seed=` is the ≤3.3 idiom). Apply every rung
  up to the target and no rung beyond it.
- **Registry findings are never skipped silently** — each is fixed or explicitly
  judged a false positive in the report.
- **Green run proves nothing about currency** — only the scanner (at the target)
  + history/catalog do.
- **Code is written in the target's idiom** — after correctness fixes, apply the
  §15b band for the target; "still works" never justifies a dated form *within
  the band*, and "it's newer" never justifies overshooting the target (and never
  experimental APIs, and never at the cost of the lesson).
- **Teaching text: minimal delta, zero staleness** — both, always. "Current"
  means current at the target. Markdown is frozen except where behavior
  changed; **comments track the code** (parity, Step 4): replace/extend/remove
  with the constructs they describe, and a migration-inserted new-at-target
  API gets a comment when the notebook's style would have one — in the
  author's language, never naming versions.
- **Claims about the model must be true of the delivered file** — a version/
  compatibility/support/tested-range sentence is a factual claim, not prose to
  freeze or a number to bump. Verify it in the Step-5 claim pass
  (`compat-support-claim`); a hedge the migration made false ("not all newer
  features supported" once the model is current-best for the target) is
  corrected or deleted. Number-matching a claim is not verifying it.
- **Pinned installs**: a `pip install mesa==old` cell becomes the target pin with
  the band-correct extras (`mesa[rec]==V` for 3.0+, plain `mesa==V` for 2.x); keep
  it commented if it was commented.
