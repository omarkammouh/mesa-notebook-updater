# mesa-notebook-updater

An [Agent Skill](https://agentskills.io) that migrates Python
[Mesa](https://github.com/mesa/mesa) (agent-based modeling) code to **any Mesa
release** — the latest by default, a pinned older version on request, in either
direction (upgrade *or* downgrade) — and keeps the surrounding teaching text
truthful while it does so.

Built for Jupyter notebooks used in teaching (exams, exercises, worked
solutions, in any natural language), but it works on plain `.py` model files
too. Use it with Claude (claude.ai, Claude Code, or the API) — or use the
bundled scanner as a standalone CLI without any AI at all.

## Why this exists

Mesa evolves fast and keeps old APIs running for several releases, often
without so much as a `DeprecationWarning`. That creates two traps this skill is
built around:

1. **Working is not updated.** A notebook that executes green on Mesa 3.5 can
   still be written entirely in the Mesa 2.x dialect. A green run proves
   nothing about currency — status must be *computed* against a target version.
2. **Nothing may be missed.** Teaching materials are the worst place for a
   stale API: one leftover `RandomActivation` in a comment teaches students an
   API that no longer exists. Completeness cannot come from eyeballing; it
   comes from a deterministic scanner that checks every code *and* markdown
   cell and is re-run until it reports zero actionable findings.

And because these are teaching materials, the prose matters as much as the
code: markdown and comments are updated in lockstep with a **minimal-delta**
contract — no added commentary, no style drift, no translation — enforced by a
machine gate plus a documented reader gate.

## What's in the box

```
skills/mesa-notebook-updater/    the skill itself (this is what gets installed)
  SKILL.md                       the workflow the model follows
  CONTRIBUTING.md                skill internals: registry schema, how to add a release
  references/
    version-catalog.json         every Mesa release ever published (89 and counting):
                                 dates, python pin, install string, curated changes
    api-registry.json            the pattern database — every API paired with a
                                 lifecycle {introduced, deprecated, superseded,
                                 removed}; status is computed at any target
    version-history.md           per-version narrative + the "current-best idiom"
                                 band table (upgrades) + the downgrade table
    notebook-editing.md          how to edit .ipynb safely (ids, outputs, magics)
  scripts/                       stdlib-only Python 3.9+ (uv needed only to execute)
    scan_notebook.py             target-conditioned scanner (code AND markdown)
    check_text_delta.py          the teaching-text gate (minimal-delta, residue,
                                 translation detection — multilingual)
    mesa_versions.py             version parsing + lifecycle math (+ self-test)
    run_notebook.py              execute a notebook pinned to any Mesa version
    normalize_notebook.py        canonicalize .ipynb via nbformat
    update_catalog.py            refresh the release catalog from PyPI
evals/                           regression suite: 8 fixture notebooks spanning
                                 Mesa 2.x -> 3.5, each with a manifest of planted
                                 findings (the grading answer key)
tools/                           repo-level checks and packaging (see CI)
```

## Install

**Claude.ai (web/desktop):** download `mesa-notebook-updater.skill` from the
[latest release](../../releases/latest) (or build it: `python3
tools/package_skill.py`), then upload it under *Settings → Capabilities →
Skills*.

**Claude Code — as a plugin:**

```
/plugin marketplace add OWNER/mesa-notebook-updater
/plugin install mesa-notebook-updater@mesa-notebook-updater
```

**Claude Code — manual:** copy the skill folder into your skills directory:

```bash
git clone https://github.com/OWNER/mesa-notebook-updater.git
cp -r mesa-notebook-updater/skills/mesa-notebook-updater ~/.claude/skills/
```

## Use

Once installed, just ask — the skill triggers on Mesa migration intent:

> Update this notebook to the latest Mesa.

> Migrate `epidemic.ipynb` to Mesa 3.3.0 — the lab machines are pinned there.

> This model was written for Mesa 2.1 and crashes with "No module named
> 'mesa.time'". Fix it.

> A colleague half-migrated this exam notebook by hand. Check whether anything
> is still old, including the explanations between the cells.

The skill establishes the target (named version, or latest from PyPI),
detects which Mesa era the model was written for, scans every cell against the
registry, applies every change the target requires — code to the current-best
idiom, prose with minimal delta — then re-scans to zero and executes the result
pinned to the target with zero Mesa warnings.

### The scanner, standalone (no AI required)

The deterministic core is useful on its own:

```bash
cd skills/mesa-notebook-updater

# what would need to change to run on 3.5.1?
python3 scripts/scan_notebook.py your_model.ipynb --target 3.5.1

# would this modern notebook survive a downgrade to the lab's 3.2.0?
python3 scripts/scan_notebook.py your_model.ipynb --target 3.2.0

# machine-readable, including matched-but-current idioms (era evidence)
python3 scripts/scan_notebook.py your_model.ipynb --target 3.5.1 --json --show-current
```

Every finding carries the API's lifecycle (introduced/deprecated/removed), its
status *at your target*, and the target-era replacement. `judge` findings are
surfaced for a human decision rather than auto-fixed.

## When a new Mesa release ships

The skill is data-driven — extending it is mostly editing three reference
files, not code. `scripts/update_catalog.py` pulls the mechanical facts from
PyPI; the curated parts (what changed, what the new best idiom is, lifecycle
stamps) are a contribution we'd love help with. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and
[skills/mesa-notebook-updater/CONTRIBUTING.md](skills/mesa-notebook-updater/CONTRIBUTING.md)
for the registry schema and the empirical-verification rules.

## Quality gates (CI)

Every push runs, stdlib-only and offline:

- `tools/validate_skill.py` — frontmatter, JSON parse, every registry regex
  compiles, every lifecycle stamp is a real catalog release, lifecycle
  self-test.
- `tools/check_fixtures.py` — the never-miss regression: 8 fixture notebooks
  with 64 planted findings; the scanner must still catch every one of them
  across upgrade and downgrade targets.
- `tools/package_skill.py` — the `.skill` bundle builds.

The deeper evals in [`evals/evals.json`](evals/evals.json) are agent-run,
graded migrations (with per-fixture answer keys in `evals/expected/`) — run
those when changing the SKILL.md workflow itself.

## Requirements

- Python ≥ 3.9 for all bundled scripts (standard library only).
- [`uv`](https://docs.astral.sh/uv/) only if you want to *execute* notebooks
  pinned to a Mesa version (`scripts/run_notebook.py`).

## License

[MIT](LICENSE) © Omar Kammouh.
