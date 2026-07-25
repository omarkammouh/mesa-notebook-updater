<!-- Keep whichever sections apply and delete the rest. -->

## What this changes

<!-- One or two sentences. If it fixes an issue, say "Fixes #123". -->

## Checks

Run from the repo root; CI runs exactly these:

- [ ] `python3 tools/validate_skill.py`
- [ ] `python3 tools/check_fixtures.py`
- [ ] `python3 tools/package_skill.py --check`

<!-- The last one fails if you edited SKILL.md, references/ or scripts/ without
     rebuilding the bundle. Run `python3 tools/package_skill.py` and commit the
     rebuilt mesa-notebook-updater.skill in this PR. -->

## If you touched the reference data

- [ ] The catalog, the registry and `version-history.md` still tell the same story.
- [ ] Every lifecycle stamp is **empirically verified**, not guessed. Paste how you
      checked:

```bash
uv run --python 3.12 --with "mesa[rec]==X.Y.Z" python -c "..."
```

<!-- Guessed stamps are the main source of wrong findings on downgrades, so this
     one matters more than it looks. Probe the release just below your claimed
     version as well as the version itself. -->

## If you changed the workflow or the idiom tables

- [ ] Ran at least one agent-graded eval from `evals/evals.json`. Which one, and
      what happened:

## Anything a reviewer should know

<!-- Behaviour changes, judgement calls, things you were unsure about. -->
