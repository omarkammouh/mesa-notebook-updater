# Contributing

This file covers the repository workflow. The skill's own
[CONTRIBUTING.md](skills/mesa-notebook-updater/CONTRIBUTING.md) covers the
internals: the registry schema, the lifecycle model, and how to verify a stamp
against a real Mesa install. Read that one before touching the reference
files.

## Source of truth

The canonical skill is `skills/mesa-notebook-updater/` in this repo. The
`.skill` bundle is a build artifact; don't commit it. CI builds it on every
push and attaches it to tagged releases.

If you also have the skill installed locally (in a skills directory your agent
loads from), that copy is where the editing happens and this one is a mirror
of it. Mirrors go stale quietly, so:

```bash
python3 tools/sync_skill.py           # compare; exits 1 if the mirror is stale
python3 tools/sync_skill.py --apply   # refresh the mirror from the installed copy
git config core.hooksPath tools/hooks # once: block commits with a stale mirror
```

Both are no-ops when the skill is not installed on your machine, so they are
harmless if you only ever work in the repo.

## What helps most

A new Mesa release shipped. Run
`python3 skills/mesa-notebook-updater/scripts/update_catalog.py`, curate the
new catalog entry, add the version-history section, stamp the registry. The
skill's CONTRIBUTING has the step-by-step.

The skill left something stale (a false negative). This is the bug class I
care most about. Include the notebook, or a minimal fixture in the style of
`evals/inputs/`, and the target version.

A false positive or a wrong replacement at some target. Include the scanner
output line and the Mesa version where you checked the actual behavior.

A new language for the text checks. `check_text_delta.py` has two word lists
(`LANG_WORDS`, `RESIDUE`) that are easy to extend.

New fixtures. A notebook that runs green on its own era's Mesa, plus a
manifest in `evals/expected/` listing every planted finding. Synthetic content
only; nothing copyrighted, nothing you can't publish under MIT.

## Before opening a PR

Run the three checks from the repo root (no network needed):

```bash
python3 tools/validate_skill.py
python3 tools/check_fixtures.py
python3 tools/package_skill.py
```

CI runs exactly these.

If you changed lifecycle stamps or replacements, verify them against a real
install and say in the PR how you checked. Every stamp in the registry was
verified this way; guessed stamps cause wrong findings on downgrades.

```bash
uv run --python 3.12 --with "mesa[rec]==X.Y.Z" python -c "..."
```

If you changed the SKILL.md workflow or the idiom tables, also run at least
one agent-graded eval from `evals/evals.json` and report the result.

Other ground rules:

- Keep the reference files consistent with each other: catalog, registry and
  version-history must tell the same story.
- Scripts stay stdlib-only, Python 3.9+. `run_notebook.py` needing `uv` is the
  one exception.
- The skill ships no example models. Fixtures live under `evals/`, never
  inside `skills/`.

## Releases

Maintainers: update `CHANGELOG.md`, tag `vX.Y.Z`, push the tag. CI attaches
the built `.skill` to the GitHub release.

## Questions

Open an issue. For "is this notebook migrated correctly" questions, attach the
scanner's `--json` output at your target; that usually settles it.
