# Changelog

Versions follow SemVer. The reference data is the public surface: a registry
or catalog refresh is a minor bump, a change to the workflow contract is a
major one.

## 1.2.0 (2026-07-25)

Fixes from runs of the skill over a four-notebook course repo.

- New SKILL.md section for **auditing a hand migration**. The description already
  advertised "check hand-migrated Mesa code", but the workflow assumed you were
  the one migrating. Two things differ and both are easy to skip: there are two
  baselines (the gates diff against the delivered file, so content the person
  added or deleted relative to the *pre-migration* original is invisible unless
  you diff for it), and a hand migration can leave the file worse than it started
  — treat a Step 6 failure as a regression until the original proves otherwise.
  Both drawn from a real audit: 10 answer-placeholder cells deleted, ASCII-art
  code cells converted to raw (a genuine fix), and a hand-typed
  `add_legend(handles=)` that broke a notebook whose original ran fine.
- New `grid-missing-random` scanner rule: a `mesa.discrete_space` grid built
  without `random=self.random` (`OrthogonalMooreGrid`, `Network`, `HexGrid`, …).
  Omitting it emits `UserWarning: Random number generator not specified` at
  construction and leaves the grid's own random draws unseeded, but the notebook
  runs green, so neither execution nor the per-line regex layer (a kwarg's
  absence is not a pattern) exposes it. The rule flattens each constructor call
  across line breaks and flags the ones with no `random=`. Judge, never blocks
  zero; the left word boundary keeps `Network(` from matching a model class like
  `VirusOnNetwork(` or the legacy `NetworkGrid(`. Found by auditing a manual
  migration that omitted it on every network model. §6.3 updated (it previously
  said this could only be caught by the semantic pass).

- A migration can now catch prose that makes a **claim about the model's
  relationship to Mesa** — "compatible with newer versions", "tested up to X",
  "not all features of newer versions are supported", "requires mesa Z" — and
  goes false once the model is brought current, even though it names no API and
  carries no wrong number. This was a real miss: bumping the version number
  inside a two-tier compatibility banner ("up-to-date with 3.0.3 / tested up to
  3.2.0 / newer features unsupported") left a sentence that was vacuous and
  false while every mechanical check stayed green. New `compat-support-claim`
  registry entry surfaces the common phrasings as judge items, a named
  claim-verification pass in SKILL.md Step 5 makes the agent check each claim
  against the delivered file, O4 and the hard rules were extended, and a
  planted finding in the `staleness_only` fixture locks it in. The fix for such
  a hedge is to correct it to the bare currency line or delete it — the
  migration changed the fact, so minimal-delta permits the deletion.


- The era estimate no longer lets a judge finding set the upper bound. Two
  `nx.spring_layout(graph, iterations=100)` calls matched the `iterations=`
  entry and were enough to report "MIXED — half-migrated notebook" about a
  notebook that scanned clean at the target. Unconfirmed matches now stay out
  of the verdict; a genuinely half-migrated notebook still reports MIXED.
- run_notebook.py labels each warning as mesa or other, and only says the
  migration is unfinished when one of them is actually Mesa's. It used to say
  that about a seaborn deprecation.
- check_report.py counts warning subclasses, so `MatplotlibDeprecationWarning`
  no longer reads as zero warnings. This makes the checker agree with the
  runner about what a warning is. **Behavior change:** a report that claimed
  `warnings_in_outputs: 0` for a notebook with non-Mesa warnings in its outputs
  will now disagree, correctly — the field is a total, and item 7 of the report
  says which of them are Mesa's.
- New registry coverage for agent removal: `grid.remove_agent(` joins
  `old-grid-methods`, and a new `model-remove-agent` entry catches teaching
  text that tells the reader to call `model.remove_agent(agent)` — a method
  that has never existed on `Model` (probed absent on 2.1.5 through 3.5.1).
  Found in the wild; it had been slipping through.
- The maintenance checklist in SKILL.md now covers the things a new release
  does not force you to touch: negative-fact entries (new
  `verified_absent_through` field), the eval target ladder, and whichever
  release calls itself "Current stable".

Repository layout, no change to the skill's behaviour:

- **The skill now lives at the repository root.** `SKILL.md`, `references/` and
  `scripts/` moved out of `skills/mesa-notebook-updater/`. This repository holds
  one skill, so the extra directory only bought a longer path. It also makes the
  simplest install the correct one: clone the repository straight into
  `~/.claude/skills/mesa-notebook-updater/` and the checkout *is* the installed
  skill, so there is nothing to copy and nothing that can drift. Claude Code
  loads a plugin whose `SKILL.md` sits at its root as a single-skill plugin, and
  the marketplace entry now points at `./`.
  If you installed by copying the old `skills/mesa-notebook-updater/` directory,
  delete it and re-clone; the plugin install path is unchanged.
- The two `CONTRIBUTING.md` files (repository workflow, skill internals) are now
  one file at the root.
- Removed `tools/sync_skill.py` and its pre-commit hook. They kept a repo copy in
  step with a separately installed copy; with the skill at the root there is no
  second copy to drift from.
- `tools/package_skill.py` now builds the bundle from an explicit include list
  (`SKILL.md`, `CONTRIBUTING.md`, `LICENSE`, `references/`, `scripts/`), so repo
  scaffolding cannot leak into a `.skill` that ships to claude.ai.
- README rewritten around the single skill, including how to use it from agents
  other than Claude.
- **`mesa-notebook-updater.skill` is now committed at the repository root**, so
  anyone on claude.ai can download one file and upload it without cloning or
  building anything. It used to be gitignored and only existed as a release
  asset, which meant it was unavailable between tags.
  A committed build artifact can go stale, so two things stop that: the zip is
  now byte-for-byte deterministic (fixed timestamps and permissions, sorted
  entries), so rebuilding an unchanged tree produces an identical file and no
  git diff; and `tools/package_skill.py --check` rebuilds into a temporary file
  and compares, which CI runs on every push and the release workflow runs before
  it attaches the bundle to a tag.
- Repository furniture for outside contributors: a code of conduct, a security
  policy that says plainly which scripts only read files and which one executes
  the notebook you point it at, a pull-request template whose checklist is the
  three CI commands, and three issue forms matching the bug classes this project
  actually gets — a missed finding, a false positive or wrong replacement, and a
  new Mesa release to catalog. The last one doubles as the maintainer's checklist.
  Also `CITATION.cff`, so the repository can be cited; `.github/dependabot.yml`
  to keep the workflow actions current (the scripts have no dependencies to
  update); and `.editorconfig`.

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
