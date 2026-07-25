# FAQ

Questions I've been asked, and the ones people are too polite to ask.
For internals — the registry schema, how to add a Mesa release — see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Using it

### How big a jump can it handle?

Any of them. Mesa 2.1 to 3.5.1 crosses about forty releases and is the case the
design is built around; the scanner prints a **migration ladder** listing every
lifecycle event between where your code sits and where you're going, version by
version.

It does not migrate in hops. You don't go 2.x → 3.0 → 3.1 → 3.2 and so on. Each
finding hands you the form that is correct **at your target**, so it's one edit
per construct, landing directly on the version you asked for. The ladder is
there so nothing between the two ends gets skipped, not as a route to walk.

### Do intermediate versions matter, or only the endpoints?

They matter, and comparing only the endpoints would be wrong. `mesa.time` is the
case that proves it: it was the scheduler module in 2.x, was deleted in 3.1, and
came back in 3.5 as the *event* module — same name, unrelated meaning. "It exists
in 2.4 and it exists in 3.5.1, so nothing to do" is a confident wrong answer.

Seventeen of the sixty-five registry entries carry per-version bands for exactly
this, so the advice changes as the target moves. For the rest, only the severity
changes across the span and the fix is the same at both ends — schedulers start
warning at 3.0 and die at 3.1, but the replacement is the AgentSet either way.

### Can it downgrade?

Yes, and it's the same machinery. Name an older target and anything newer than it
reports as `not-yet-introduced` — that list *is* the work list. This is for when
your lab machines or a shared cluster are pinned to something older than your
laptop.

Downgrades are less safe than upgrades, and the skill says so rather than
pretending otherwise: some things have no clean reversal (moving `model.rng`
draws back to `self.random` changes the random sequence), and it will not move
your code onto an experimental module just to satisfy a downgrade.

### Does it work on plain `.py` files?

Yes. The scanner and the text checks take `.py` unchanged. Only the notebook
mechanics differ — the execution step uses an import-and-step harness instead of
running cells, and the notebook canonicalizer doesn't apply.

### Do I need Claude?

No. `SKILL.md` is a markdown workflow and the scripts are standard-library
Python, so any agent that reads files and runs shell commands can follow it —
see [Other agents](README.md#other-agents) in the README.

You can also skip the agent entirely. `scan_notebook.py` on its own tells you
what would need to change and why, which is often all you want before deciding
whether to migrate at all.

### Can it do a whole folder at once?

Yes, one notebook at a time. Each gets its own scan, its own pinned run and its
own report. Ask for the folder and let it work through them.

## What it will and won't do to my files

### Will it rewrite my teaching text?

As little as it can. Code is rewritten to the target's idiom; prose is held to a
**minimal-delta contract** — no added explanations, no tone changes, no
translation, no "this used to be `RandomActivation`" commentary. If a paragraph
explains a mechanism that genuinely changed, it gets rewritten in your voice at
roughly the same length. Everything else should come back byte-identical.

That isn't a promise on trust: `check_text_delta.py` diffs the prose against the
original and flags added markdown, removed cells, changed cell counts, migration
residue, a cell whose length moved by more than a sentence, and a cell whose
language flipped. All of those must be zero.

### Will it reorganize my notebook?

No. Same cells, same order, same cell ids, same markdown. Adding, removing or
reordering cells is a contract violation and the checks fail on it. Your variable
names and code structure are kept too — modernizing an idiom is not a licence to
tidy.

### Will my results change?

Sometimes, and the report says exactly where and why. Two common causes: moving
from `seed=` to `rng=` changes the random sequence, so a seeded run won't
reproduce its old numbers; and creating agents in one broadcast call instead of a
loop reorders random draws. Both are statistically equivalent, not regressions.

Occasionally a change is a genuine correction, and those are worth reading. In one
real migration, an exercise called `model.G.remove_edge()` on a network space —
which removes the graph edge but leaves the agents' neighbourhoods untouched, so
the "disconnection" did nothing. Fixing it changed the plots, because the exercise
had never actually worked.

### Can I undo it?

The skill edits in place and keeps no backups, on the assumption your files are
in version control. It checks that before the first edit: if the file isn't
tracked and clean, it snapshots the original elsewhere first, because the
verification steps diff against it.

If you're not using git, copy the folder before you start.

### Does it run my code? Does it send my notebook anywhere?

The scanner and the text checks only read files. The execution step **does** run
your notebook, in a kernel with the target Mesa installed — a migration isn't
finished until the thing runs. Nothing is uploaded. The only script that touches
the network on its own is the catalog refresher, which reads release metadata
from PyPI. See [SECURITY.md](.github/SECURITY.md).

### What if my notebook doesn't run top to bottom?

Common in teaching material, and it's handled without pretending. Course notebooks
often have cells that aren't Python at all — ASCII-art diagrams the author meant
as markdown — which stop any linear run with a `SyntaxError` that has nothing to
do with Mesa.

The skill confirms the problem is pre-existing rather than something it caused,
leaves the cells alone (converting them would break the structure contract),
verifies the Mesa code by extraction instead, and says plainly in the report that
the run was not a clean linear green. It will not report a false green.

## How it knows what changed in Mesa

### How does it know that X was replaced by Y?

Someone wrote it down. There's no inference: each API has an entry recording when
it appeared, when it started warning, when a better form arrived, and when it
died, plus the replacement text. The scanner compares your target against those
stamps and computes a status.

That sounds unglamorous, and it is. It's also the only thing that works, because
the information doesn't exist at runtime — see the next question.

### Both the old and the new way still work. How would it know to prefer the new one?

This is the case the project exists for, and it has its own status: `legacy`.

On Mesa 3.5.1, the old `mesa.space.MultiGrid` constructs perfectly happily and
raises **zero warnings**. Your tests pass. Python has no opinion. Nothing at
runtime will ever tell you that `OrthogonalMooreGrid` superseded it in 3.2 — the
fact only exists in Mesa's migration guide and in someone's head.

So the registry records it as `superseded: 3.2.0` with the replacement spelled
out, and the scanner reports it as `legacy`: runs fine, superseded, migrate
anyway. That's distinct from `deprecated` (warns at you) and `removed` (crashes).
A tool that only looks for warnings or failures is blind to this entire category.

### How do you know the version numbers are right?

Every stamp was checked against a real install rather than taken from a changelog,
because release notes announce features and rarely pin the exact release where
something starts warning:

```bash
uv run --python 3.12 --with "mesa[rec]==3.0.3" python -c \
  "import mesa; print(hasattr(type('A',(mesa.Agent,),{}), 'create_agents'))"
```

That's how you learn `create_agents` doesn't exist at 3.0.3 but does at 3.1. Both
sides of the boundary get probed, since an off-by-one stamp produces wrong
findings on downgrades. CI checks that stamps are internally consistent — each
resolves to a real catalogued release — but it cannot check that they're *true*.
Only the probe does that.

## When it gets something wrong

### What if it misses something?

That's the failure mode I care most about, and it's the one to report. A missed
API in teaching material means a student learns something that no longer exists.
Use the [missed-finding issue form](.github/ISSUE_TEMPLATE/missed-finding.yml);
it asks for the target, the line that stayed stale, and the scanner's JSON.

The skill is a careful set of notes about Mesa, and notes can have holes. If
nobody ever recorded that X was replaced by Y, the scan comes back clean while
your code sits in a dead dialect.

### What are `judge` findings? Do I have to fix them?

No — they're deliberate. Some patterns are ambiguous: `seed=` might belong to
numpy rather than Mesa, `iterations=` might be a networkx layout parameter (it
usually is). Rather than guess, the scanner surfaces them for a human and doesn't
let them block completion.

A correct migration normally ends with a handful. The report has to say what
happened to each one — fixed, false positive and why, or correctly left alone —
so they're accounted for rather than ignored.

### It flagged something that's fine. Is that a bug?

If it's a `judge` item, no — that's the design. If something with a hard status
(`removed`, `deprecated`, `legacy`, `not-yet-introduced`) is wrong at your target,
that's a real bug and worth reporting, with a pinned probe showing Mesa's actual
behaviour. Same standard the stamps were written to.

### How do I check the migration myself?

The checks are deterministic and run on their own, whatever produced the result:

```bash
python3 scripts/scan_notebook.py migrated.ipynb --target 3.5.1
python3 scripts/check_text_delta.py original.ipynb migrated.ipynb --target 3.5.1
```

Zero actionable findings from the first, zero hard flags from the second. If the
migration produced a report, `check_report.py` re-derives every number in it from
the delivered notebook, so a summary can't claim a run or a count that didn't
happen.

## Keeping it current

### Mesa just released a new version. Does the skill still work?

It works, but it doesn't know about the new release until someone adds it, and
it'll keep targeting the latest version it *does* know. Adding one is mostly data
entry: `update_catalog.py` pulls the mechanical facts from PyPI and the curated
part (what changed, new idioms, lifecycle stamps) is written by hand.
[CONTRIBUTING.md](CONTRIBUTING.md) has the steps, and the
[new-release issue form](.github/ISSUE_TEMPLATE/new-mesa-release.yml) doubles as
the checklist.

### What does it need installed?

Python 3.9 or newer, standard library only, for everything except two scripts:
running a notebook pinned to a Mesa version needs [`uv`](https://docs.astral.sh/uv/),
and canonicalizing a notebook needs `nbformat` (which `uv` can supply on the fly).
Nothing to `pip install` to use the scanner.
