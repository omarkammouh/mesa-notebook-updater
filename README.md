# mesa-notebook-updater

[![CI](https://github.com/omarkammouh/mesa-notebook-updater/actions/workflows/ci.yml/badge.svg)](https://github.com/omarkammouh/mesa-notebook-updater/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Mesa releases cataloged](https://img.shields.io/badge/Mesa%20releases%20cataloged-91-blue.svg)](references/version-catalog.json)

An [Agent Skill](https://agentskills.io) that migrates
[Mesa](https://github.com/mesa/mesa) agent-based models between Mesa versions.
Point it at a notebook (or a plain `.py` model) and a target version and it
brings the code there, in either direction: an old 2.x model up to current
Mesa, or modern code down to whatever your lab machines are pinned to. If you
don't name a version, it targets the latest release.

I built this for my own teaching notebooks, so it cares as much about the text
between the cells as about the code. It works with Claude, and with any other
agent that can read files and run shell commands — see
[Other agents](#other-agents). The bundled scanner also runs on its own, with
no agent at all.

**A ready-to-load bundle is checked in**:
[`mesa-notebook-updater.skill`](mesa-notebook-updater.skill) at the root of this
repository. Download that one file and upload it to claude.ai; you don't have to
clone anything or build it. It is rebuilt from the sources on every change, and
CI fails if it falls out of step.

## Why

Two things make hand-migrating Mesa material unreliable.

First, Mesa keeps old APIs working for a long time, often without any warning.
A notebook that runs fine on Mesa 3.5 can still be written entirely in the
2.x dialect, so "it runs" tells you nothing. Whether something is current
depends on the target version, and has to be computed, not eyeballed.

Second, it is very easy to miss one instance. In teaching material that
matters more than usual: a single leftover `RandomActivation` in a comment
teaches students an API that no longer exists. The skill therefore relies on a
deterministic scanner that checks every code and markdown cell against a
lifecycle database of the API, and repeats until nothing actionable is left.

The markdown gets the opposite treatment from the code: code is rewritten to
the idiom that is current at the target, while prose is changed as little as
possible (no added commentary, no tone shift, no translation). A separate
script checks that contract.

## How it knows what changed

There is no version-to-version diff table anywhere in here. Instead each Mesa API
gets one entry recording its biography — when it appeared, when it started
warning, when a better form arrived, when it died — and the status at your target
is computed by comparing the two. Sixty-five entries cover what 91 releases would
otherwise need 4095 pairwise diffs to express.

Four states, and the third is the one that matters most:

| | |
|---|---|
| `not-yet-introduced` | doesn't exist at your target — the downgrade work list |
| `removed` | errors at your target |
| `deprecated` | runs, but warns |
| **`legacy`** | **runs silently, superseded, migrate anyway** |

That last one is why the project exists. On Mesa 3.5.1 the old
`mesa.space.MultiGrid` builds fine and raises zero warnings — nothing at runtime
will ever tell you that `OrthogonalMooreGrid` replaced it in 3.2. That fact lives
in Mesa's migration guide, so it was written down here, verified against a real
install, and is now applied mechanically every time.

**Big jumps are the normal case, not the hard one.** Migrating a Mesa 2.x
notebook to 3.5.1 crosses about forty releases; the scanner prints a *migration
ladder* of every lifecycle event in between, so nothing gets skipped. It doesn't
migrate in hops — each finding gives you the form that is correct at your target,
so it's one edit per construct. Where the right answer genuinely changes partway
through the jump, the entry carries per-version bands: `mesa.time` was the
scheduler module, was deleted in 3.1, and returned in 3.5 meaning something
completely different, and comparing only the endpoints would miss that entirely.

More on all of this, including what it won't touch and what to do when it gets
something wrong, in the [FAQ](FAQ.md).

## Install

### Claude Code

Clone the repository straight into your skills directory. The repository *is*
the skill, so there is no copy step and nothing to keep in sync:

```bash
git clone https://github.com/omarkammouh/mesa-notebook-updater.git \
  ~/.claude/skills/mesa-notebook-updater
```

`git pull` in that directory is how you update. To make it available in one
project only, clone into `.claude/skills/mesa-notebook-updater` inside that
project instead.

### Claude Code, as a plugin

```
/plugin marketplace add omarkammouh/mesa-notebook-updater
/plugin install mesa-notebook-updater@mesa-notebook-updater
```

### claude.ai (web or desktop)

Download [`mesa-notebook-updater.skill`](mesa-notebook-updater.skill) from this
repository — on the file's page, use the download button — and upload it under
Settings, Capabilities, Skills. Nothing to build.

The same file is attached to every [tagged release](../../releases/latest) if you
would rather pin a version, and `python3 tools/package_skill.py` rebuilds it from
the sources.

### Other agents

Nothing here is Claude-specific. `SKILL.md` is a plain markdown workflow, and
the scripts are standard-library Python that any agent can run through its
shell tool. To use it from Codex, Cursor, Copilot, Gemini CLI or anything else,
clone the repository anywhere and point the agent at the file:

```bash
git clone https://github.com/omarkammouh/mesa-notebook-updater.git ~/skills/mesa-notebook-updater
```

Then ask, in whatever agent you are using:

> Read ~/skills/mesa-notebook-updater/SKILL.md and follow that workflow to
> migrate model.ipynb to the latest Mesa.

For agents that read a project file automatically — Codex and several others
use `AGENTS.md` — add the pointer there once and drop the path from your
prompts:

```markdown
## Migrating Mesa notebooks

Follow ~/skills/mesa-notebook-updater/SKILL.md. Run its scripts by absolute
path and keep the working directory in this project.
```

The one thing to keep an eye on with a non-Claude agent is that `SKILL.md`
asks for a specific discipline — re-scan until zero, don't overshoot the
target, leave the prose alone — and a weaker agent will drift from it. The
checks in `scripts/` are there for exactly that reason: `scan_notebook.py`,
`check_text_delta.py` and `check_report.py` are deterministic, so you can
verify the result whatever produced it.

## Usage

Once installed it triggers on normal requests, for example:

> Update this notebook to the latest Mesa.

> Migrate epidemic.ipynb to Mesa 3.3.0, the lab machines are pinned there.

> This model was written for Mesa 2.1 and crashes with "No module named
> 'mesa.time'". Fix it.

> A colleague half-migrated this exam notebook by hand. Check whether anything
> is still old, including the explanations between the cells.

The skill figures out the target, detects which Mesa era the model was written
for, scans, applies what the target requires, re-scans until clean, and
finally executes the notebook pinned to the target and expects zero Mesa
warnings.

### Using the scanner directly

The scanner is useful on its own, and needs nothing but Python:

```bash
# what would need to change to run on 3.5.1?
python3 scripts/scan_notebook.py your_model.ipynb --target 3.5.1

# would this modern notebook survive a downgrade to 3.2.0?
python3 scripts/scan_notebook.py your_model.ipynb --target 3.2.0

# machine-readable, including matched-but-current idioms
python3 scripts/scan_notebook.py your_model.ipynb --target 3.5.1 --json --show-current
```

Each finding shows the API's lifecycle, its status at your target, and the
replacement for that target. Findings marked `judge` are ambiguous on purpose
and left for a human.

## Layout

The skill sits at the repository root; the rest is scaffolding for testing and
packaging it.

```
SKILL.md                 the workflow
references/
  version-catalog.json   every Mesa release (91 at last count): dates, python
                         pin, install string, what changed
  api-registry.json      API patterns with lifecycle stamps (introduced,
                         deprecated, superseded, removed)
  version-history.md     per-version notes, plus the "best idiom at this
                         target" tables for upgrades and downgrades
  notebook-editing.md    editing .ipynb files without breaking them
scripts/                 stdlib Python 3.9+; uv only needed to execute notebooks
  scan_notebook.py       the scanner (code and markdown)
  check_text_delta.py    the teaching-text check
  check_report.py        checks the final report's facts block against the
                         delivered file, so the summary can't lie
  mesa_versions.py       version parsing and lifecycle math
  run_notebook.py        run a notebook pinned to a given Mesa version
  normalize_notebook.py  canonicalize .ipynb
  update_catalog.py      refresh the catalog from PyPI
mesa-notebook-updater.skill   the packaged bundle, ready to upload to claude.ai;
                         built from the files above by tools/package_skill.py
evals/                   8 fixture notebooks with answer keys, see evals/README.md
tools/                   repo checks and packaging, used by CI
CONTRIBUTING.md          internals: registry schema, adding a Mesa release
FAQ.md                   what it will and won't change, and how it knows
```

## When a new Mesa version comes out

The skill is data-driven, so keeping it current mostly means editing the three
reference files rather than the code. `scripts/update_catalog.py` pulls the
mechanical facts from PyPI; the curated parts (what changed, new best idioms,
lifecycle stamps) have to be added by hand. [CONTRIBUTING.md](CONTRIBUTING.md)
has the step-by-step and the registry schema. PRs welcome.

## CI

Every push runs three checks, offline and stdlib-only:

- `tools/validate_skill.py`: frontmatter, JSON, every registry regex compiles,
  every lifecycle stamp points at a real release.
- `tools/check_fixtures.py`: the scanner must still catch all 65 planted
  findings in the fixture notebooks, across upgrade and downgrade targets.
- `tools/package_skill.py --check`: the committed `.skill` still matches
  `SKILL.md`, `references/` and `scripts/`. The build is byte-for-byte
  deterministic, so this fails only when someone edits the skill and forgets to
  rebuild the bundle.

The evals in `evals/evals.json` go further (full agent-run migrations, graded
against answer keys) and are run manually when the workflow itself changes.

## Requirements

Python 3.9 or newer, standard library only. [`uv`](https://docs.astral.sh/uv/)
is needed only to execute notebooks pinned to a specific Mesa version, and
`nbformat` (via `uv run --with nbformat`) only for `normalize_notebook.py`.

## Contributing and support

The [FAQ](FAQ.md) covers the common worries — what it changes, what it leaves
alone, whether your results will move, and what to do when it gets something
wrong. Bug reports, especially "the skill left something stale", are the most
useful thing you can send. [CONTRIBUTING.md](CONTRIBUTING.md) covers the internals and
what each kind of report needs; the issue templates ask for the same things.
Security reports go through a [private advisory](.github/SECURITY.md).

## Citing

If this saved you a week of migrating course notebooks and you'd like to say so
in a paper, [CITATION.cff](CITATION.cff) has the metadata, and GitHub's
"Cite this repository" button renders it as BibTeX or APA.

## License

[MIT](LICENSE), Omar Kammouh.
