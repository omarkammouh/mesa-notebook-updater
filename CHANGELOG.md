# Changelog

Versions follow SemVer. The reference data is the public surface: a registry
or catalog refresh is a minor bump, a change to the workflow contract is a
major one.

## 1.1.0 (2026-07-24)

A knowledge and gates refresh; no change to how you use the skill.

- The API registry grew from 50 to 63 entries, and the catalog now lists 91
  releases (the 3.5.0b0 and 4.0.0a0 pre-releases are cataloged too).
- The scanner got several semantic rules on top of the regex layer: base-class
  choice for discrete_space grids, the pre-3.0 scheduler clock, multi-line
  call handling, comment coverage around findings, and a better era ladder
  from the evidence it collects.
- check_text_delta is now registry-aware: with --target it also flags prose
  that describes an API from the wrong era, in comments as well as markdown.
- New script check_report.py: the skill's final report must carry a facts
  block, and this checks every line of it against the delivered notebook, so
  a summary can't claim an execution or a count that didn't happen.
- normalize_notebook.py grew from a thin nbformat wrapper into the mandatory
  finishing gate (validates, restores canonical serialization, fails loudly).
- SKILL.md and the reference files were extended to match; the workflow now
  ends with the verified report step.

## 1.0.0 (2026-07-20)

First public release.

The skill migrates Mesa notebooks and `.py` models to any of the 89 cataloged
Mesa releases, upgrading or downgrading, rewriting code to the idiom that is
current at the target while keeping the teaching text as close to the
original as possible.

Included:

- Reference data: full release catalog, API registry with lifecycle stamps
  (all verified against real installs), per-version history with upgrade and
  downgrade idiom tables, notes on safe .ipynb editing.
- Scripts (stdlib, Python 3.9+): the target-conditioned scanner for code and
  markdown, the teaching-text delta check (multilingual), lifecycle math with
  a self-test, a pinned notebook runner (needs uv), a notebook normalizer,
  and a PyPI catalog updater.
- Evals: 8 fixture notebooks spanning Mesa 2.x to 3.5, each with an answer
  key of planted findings.
- Repo tooling and CI: structural validation, a regression check that the
  scanner still catches all 64 planted findings, and packaging. Tagged
  releases get the .skill bundle attached.
