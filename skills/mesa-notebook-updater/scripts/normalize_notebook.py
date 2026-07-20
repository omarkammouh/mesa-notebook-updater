#!/usr/bin/env python3
"""Canonicalize notebooks: nbformat read -> validate -> write, in place.

The mandatory finishing gate after editing. Restores Jupyter's canonical
serialization (list-of-lines sources, indent, trailing newline), erasing
artifacts left by NotebookEdit (single-string sources, cleared trailing
newline) or ad-hoc JSON edits, and fails loudly on schema violations.

Usage:
    uv run --with nbformat python normalize_notebook.py NB.ipynb [MORE.ipynb ...]

Exit codes: 0 = all normalized and valid; 3 = at least one validation error
(file is still written so you can inspect it).
"""
import sys

import nbformat


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    status = 0
    for path in sys.argv[1:]:
        nb = nbformat.read(path, as_version=4)
        try:
            nbformat.validate(nb)
        except nbformat.ValidationError as exc:
            first_line = str(exc).splitlines()[0] if str(exc) else repr(exc)
            print(f"{path}: VALIDATION ERROR: {first_line}")
            status = 3
        nbformat.write(nb, path)
        print(f"{path}: normalized")
    return status


if __name__ == "__main__":
    sys.exit(main())
