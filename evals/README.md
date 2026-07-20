# Evals

Regression suite for the skill. All fixtures are **synthetic** teaching-style
notebooks written for this project — no real course material.

- `inputs/` — 8 notebooks, each of which runs green on its *own* era's Mesa
  (see `runs_on` in its manifest). They span Mesa 2.x classics, a pinned 3.3
  model, modern 3.5 code (a downgrade test), a half-migrated bilingual exam, a
  "green but dead" dialect test, and a prose-staleness-only test.
- `expected/<name>.manifest.json` — the grading answer key per fixture: era,
  execution pin, protected cells (must stay byte-identical), and
  `planted_findings` — every issue deliberately planted, by registry `api_id`.
  **Never show a manifest to the agent being evaluated.**
- `evals.json` — the agent-run eval definitions: a realistic user prompt per
  fixture plus the assertions a grader checks after the migration (scanner
  clean at target, pinned execution green with zero Mesa warnings, protected
  cells untouched, no migration residue in the text).

Two layers of use:

1. **Deterministic (CI):** `python3 tools/check_fixtures.py` from the repo
   root asserts the scanner still catches every regex-backed planted finding
   across upgrade and downgrade targets. Runs offline in seconds.
2. **Agent-graded (manual):** run a fixture's prompt from `evals.json` against
   the installed skill on a *copy* of the input, then check every assertion
   (and the manifest) yourself or with a second model as grader. Do this
   whenever `SKILL.md` or the idiom tables change.

A handful of planted findings (e.g. `run-loop`, `manual-agent-creation`) have
no registry entry on purpose: they are semantic judgment calls the workflow's
modernization checklist catches, not regexes. The deterministic layer skips
them; the agent-graded layer is where they count.
