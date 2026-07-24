# mesa-notebook-updater

A Claude [Agent Skill](https://agentskills.io) that migrates
[Mesa](https://github.com/mesa/mesa) agent-based models between Mesa versions.
Point it at a notebook (or a plain `.py` model) and a target version and it
brings the code there, in either direction: an old 2.x model up to current
Mesa, or modern code down to whatever your lab machines are pinned to. If you
don't name a version, it targets the latest release.

I built this for my own teaching notebooks, so it cares as much about the text
between the cells as about the code. The bundled scanner is also usable on its
own, without Claude.

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

## Layout

```
skills/mesa-notebook-updater/   the skill itself; this is what gets installed
  SKILL.md                      the workflow
  CONTRIBUTING.md               internals: registry schema, adding a release
  references/
    version-catalog.json        every Mesa release (91 at last count): dates,
                                python pin, install string, what changed
    api-registry.json           API patterns with lifecycle stamps (introduced,
                                deprecated, superseded, removed)
    version-history.md          per-version notes, plus the "best idiom at this
                                target" tables for upgrades and downgrades
    notebook-editing.md         editing .ipynb files without breaking them
  scripts/                      stdlib Python 3.9+; uv only needed to execute
    scan_notebook.py            the scanner (code and markdown)
    check_text_delta.py         the teaching-text check
    check_report.py             checks the final report's facts block against
                                the delivered file, so the summary can't lie
    mesa_versions.py            version parsing and lifecycle math
    run_notebook.py             run a notebook pinned to a given Mesa version
    normalize_notebook.py       canonicalize .ipynb
    update_catalog.py           refresh the catalog from PyPI
evals/                          8 fixture notebooks with answer keys, see evals/README.md
tools/                          repo checks and packaging, used by CI
```

## Install

Claude.ai (web or desktop): download `mesa-notebook-updater.skill` from the
[latest release](../../releases/latest), or build it yourself with
`python3 tools/package_skill.py`, and upload it under Settings, Capabilities,
Skills.

Claude Code, as a plugin:

```
/plugin marketplace add omarkammouh/mesa-notebook-updater
/plugin install mesa-notebook-updater@mesa-notebook-updater
```

Claude Code, manually:

```bash
git clone https://github.com/omarkammouh/mesa-notebook-updater.git
cp -r mesa-notebook-updater/skills/mesa-notebook-updater ~/.claude/skills/
```

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

```bash
cd skills/mesa-notebook-updater

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

## When a new Mesa version comes out

The skill is data-driven, so keeping it current mostly means editing the three
reference files rather than code. `scripts/update_catalog.py` pulls the
mechanical facts from PyPI; the curated parts (what changed, new best idioms,
lifecycle stamps) have to be added by hand. See [CONTRIBUTING.md](CONTRIBUTING.md)
for the repo side and
[skills/mesa-notebook-updater/CONTRIBUTING.md](skills/mesa-notebook-updater/CONTRIBUTING.md)
for the schema and the verification rules. PRs welcome.

## CI

Every push runs three checks, offline and stdlib-only:

- `tools/validate_skill.py`: frontmatter, JSON, every registry regex compiles,
  every lifecycle stamp points at a real release.
- `tools/check_fixtures.py`: the scanner must still catch all 64 planted
  findings in the fixture notebooks, across upgrade and downgrade targets.
- `tools/package_skill.py`: the bundle still builds.

The evals in `evals/evals.json` go further (full agent-run migrations, graded
against answer keys) and are run manually when the workflow itself changes.

## Requirements

Python 3.9 or newer, standard library only. [`uv`](https://docs.astral.sh/uv/)
is needed only to execute notebooks pinned to a specific Mesa version.

## License

[MIT](LICENSE), Omar Kammouh.
