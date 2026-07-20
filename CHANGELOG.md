# Changelog

Versions follow SemVer. The reference data is the public surface: a registry
or catalog refresh is a minor bump, a change to the workflow contract is a
major one.

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
