# Evals

Regression suite for the skill. All fixtures are synthetic, written for this
project; there is no real course material here.

`inputs/` holds 8 notebooks. Each runs green on its own era's Mesa (the
`runs_on` field in its manifest). They cover Mesa 2.x classics, a pinned 3.3
model, modern 3.5 code (used as a downgrade test), a half-migrated bilingual
exam, a "green but dead" dialect test, and one notebook where only the prose
is stale.

`expected/<name>.manifest.json` is the answer key for each fixture: era,
execution pin, protected cells that must stay byte-identical, and
`planted_findings`, every issue that was deliberately planted, by registry
`api_id`. Don't show a manifest to the agent being evaluated.

`evals.json` holds the agent-run eval definitions: a realistic user prompt
per fixture and the assertions a grader checks afterwards (scanner clean at
the target, pinned execution with zero Mesa warnings, protected cells
untouched, no migration residue in the text).

Two ways to use this:

1. Deterministic, in CI: `python3 tools/check_fixtures.py` from the repo root
   asserts the scanner still catches every regex-backed planted finding,
   across upgrade and downgrade targets. Offline, takes seconds.
2. Agent-graded, manually: run a fixture's prompt from `evals.json` against
   the installed skill on a copy of the input, then check the assertions and
   the manifest, yourself or with a second model as grader. Do this whenever
   SKILL.md or the idiom tables change.

A few planted findings (`run-loop`, `manual-agent-creation`) have no registry
entry on purpose: they are judgment calls the workflow's modernization
checklist handles, not regexes. The deterministic layer skips them; they only
count in the agent-graded runs.
