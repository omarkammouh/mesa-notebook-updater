# Contributing

Thanks for helping keep Mesa migrations complete and honest. This file covers
the **repository workflow**; the skill's own
[CONTRIBUTING.md](skills/mesa-notebook-updater/CONTRIBUTING.md) covers the
**internals** — the registry schema, the lifecycle model, and how to verify a
stamp empirically. Read both before a non-trivial PR.

## Source of truth

`skills/mesa-notebook-updater/` in this repository is the canonical skill.
The distributable `.skill` bundle is a build artifact — never commit it; CI
builds it on every push and attaches it to releases on tags.

## The most valuable contributions

1. **A new Mesa release shipped.** Run `python3
   skills/mesa-notebook-updater/scripts/update_catalog.py`, curate the new
   catalog entry, append the version-history section, and stamp the registry.
   The step-by-step is in the skill's CONTRIBUTING.
2. **A false negative** — the skill left something stale. This is the bug class
   we care most about ("nothing gets missed"). Please include the notebook (or
   a minimal fixture built like `evals/inputs/*`) and the target version.
3. **A false positive / wrong replacement** at some target — include the
   scanner output line and the Mesa version where you verified the correct
   behavior.
4. **A new language** for the teaching-text gate — extend `LANG_WORDS` /
   `RESIDUE` in `scripts/check_text_delta.py` with your language's function
   words and migration-commentary phrases.
5. **New eval fixtures** — a notebook that runs green on its own era's Mesa,
   plus an `evals/expected/<name>.manifest.json` answer key listing every
   planted finding. Synthetic content only: no copyrighted course material,
   nothing you can't publish under MIT.

## Before you open a PR

Run the three repo checks from the repo root (stdlib only, no network):

```bash
python3 tools/validate_skill.py    # structure, regexes, lifecycle stamps
python3 tools/check_fixtures.py    # the never-miss regression suite
python3 tools/package_skill.py     # the bundle still builds
```

CI runs exactly these, so green locally means green on the PR.

If you changed lifecycle stamps or replacements, verify them against a real
install (this is a hard rule — every stamp in the registry is empirically
verified):

```bash
uv run --python 3.12 --with "mesa[rec]==X.Y.Z" python -c "..."
```

and say in the PR **how** you checked. If you changed the SKILL.md workflow or
the §15b/§15c idiom tables, also run at least one agent-graded eval from
`evals/evals.json` and report the result.

## PR checklist

- [ ] The three `tools/` checks pass locally.
- [ ] Reference files stay in lockstep: catalog ↔ registry ↔ version-history
      tell the same story.
- [ ] New/changed lifecycle stamps state their empirical verification.
- [ ] Scripts remain stdlib-only, Python ≥ 3.9 (`run_notebook.py`'s `uv`
      dependency is the only exception).
- [ ] The skill ships no example models — fixtures live under `evals/`, never
      inside `skills/`.
- [ ] No AI-tell prose in migrated text or docs ("seamlessly", "Note that…") —
      the same reader gate the skill enforces applies to this repo.

## Releases

Maintainers: bump `CHANGELOG.md`, tag `vX.Y.Z`, push the tag. CI builds
`mesa-notebook-updater.skill` and attaches it to the GitHub release. Claude.ai
users install from that file; plugin users just pull the repo.

## Questions / discussion

Open a GitHub issue. For "is this notebook migrated correctly?" questions,
attach the scanner's `--json` output at your target — it usually answers the
question by itself.
