# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[SemVer](https://semver.org/) (the skill's data files are the public surface —
a registry/catalog refresh is a minor bump, a workflow-contract change is a
major one).

## [1.0.0] — 2026-07-20

First public release.

### Added

- **The skill** (`skills/mesa-notebook-updater/`): target-conditioned Mesa
  migration for notebooks and `.py` models — upgrade, downgrade, or pin to any
  of the 89 cataloged Mesa releases; current-best-idiom code changes with
  minimal-delta teaching-text changes.
- **Reference data**: full release catalog (`version-catalog.json`), lifecycle
  pattern registry (`api-registry.json`, schema v2, every stamp empirically
  verified), per-version narrative with upgrade band table and downgrade table
  (`version-history.md`), safe `.ipynb` editing notes.
- **Scripts** (stdlib, Python ≥ 3.9): target-conditioned scanner over code and
  markdown, multilingual teaching-text delta gate, lifecycle math with
  self-test, pinned notebook runner (`uv`), notebook normalizer, PyPI catalog
  updater.
- **Regression evals** (`evals/`): 8 fixture notebooks spanning Mesa 2.x→3.5
  (classic money model, epidemic grid, boids, traffic, Schelling, mixed-era
  exam, green-but-dead, staleness-only) with planted-finding answer keys.
- **Repo tooling** (`tools/`): structural validator, never-miss fixture check
  (64 regex-backed planted findings across three targets), `.skill` packager.
- **CI**: validation + regression + packaging on every push; `.skill` bundle
  attached to tagged releases.
