# Security

## Reporting a vulnerability

Report privately through GitHub's
[security advisory form](https://github.com/omarkammouh/mesa-notebook-updater/security/advisories/new),
not as a public issue. I'll acknowledge within a week.

## What this project does, and what that means

Two parts of this repository run code, and you should know which:

- **The scanner and the text checks** (`scan_notebook.py`, `check_text_delta.py`,
  `check_report.py`, `mesa_versions.py`) only read files. They parse notebooks as
  JSON and match regexes against the source; they never execute a notebook's code.
- **`run_notebook.py` executes the notebook you point it at**, in a Jupyter kernel,
  with a Mesa version installed on the fly through `uv`. That is the whole point of
  the step — a migration is not finished until the notebook runs — but it means
  running it on a notebook you did not write is equivalent to running that
  notebook's code yourself. `update_catalog.py` is the only script that reaches the
  network on its own, and only to fetch release metadata from PyPI.

The skill also installs Mesa from PyPI at the version you target. Those are
upstream packages; this project does not vendor or verify them.

## Agent Skills specifically

A skill directs an agent's behaviour, so treat installing one like installing
software: read `SKILL.md` and the scripts before you run them, and prefer a
tagged release or a commit you have looked at over an arbitrary branch. Anthropic's
[Agent Skills security guidance](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview#security-considerations)
covers the general case.

Everything here is plain text and standard-library Python precisely so it can be
audited: no build step, no binary except `mesa-notebook-updater.skill`, which is a
zip of the very files sitting next to it and is rebuilt and checked in CI on every
push (`tools/package_skill.py --check`).

## Supported versions

The latest tagged release gets fixes. The reference data (API registry, version
catalog) is the part that goes out of date; a stale catalog produces wrong
migration advice rather than a vulnerability, but please report it as a bug.
