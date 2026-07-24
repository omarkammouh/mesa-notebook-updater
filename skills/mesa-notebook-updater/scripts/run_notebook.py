#!/usr/bin/env python3
"""Execute a Jupyter notebook in place and report the first error compactly.

Usage:
    python run_notebook.py NOTEBOOK.ipynb [--timeout SECONDS]

Exit codes: 0 = every cell ran; 1 = a cell errored or timed out (compact
details printed to stdout); 2 = could not read/parse the notebook.

Run inside an ephemeral environment pinned to the target Mesa, e.g.:
    uv run --python 3.12 --with "mesa[rec]==X.Y.Z" --with nbclient --with ipykernel \
        python run_notebook.py notebook.ipynb

The notebook is written back in place with the outputs of whatever executed,
so after a failure you can inspect partial outputs; after success the notebook
carries fresh outputs from the target Mesa version.
"""
import argparse
import os
import re
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError, CellTimeoutError, DeadKernelError

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
WARN_LINE = re.compile(r"\b\w*(?:Deprecation|Future|User|Runtime)Warning\b")
# Attribution, not detection: which of the warning lines above blame mesa. A
# warning line is `path/to/file.py:LINE: SomeWarning: message`, so the emitting
# package shows up as a path segment; the message body is checked too, for
# warnings raised through a logging shim.
MESA_WARN = re.compile(r"[/\\]mesa[/\\]|\bmesa\.\w|\bMesa\b")


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text)


def excerpt(source: str, max_lines: int = 15) -> str:
    lines = source.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n… (+{len(lines) - max_lines} more lines)"
    return source


def report_warnings(nb) -> None:
    """Print unique warning lines from cell outputs, split by who emitted them.

    A Mesa Deprecation/FutureWarning means the migration is not finished. A
    warning from matplotlib/seaborn/pandas means the plotting stack moved on
    and is out of scope unless it blocks the run (SKILL.md Step 6) — saying
    "the migration is not finished" about one of those sends the reader
    hunting for a Mesa problem that is not there.
    """
    seen = {}
    for abs_idx, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        for out in cell.get("outputs", []):
            if out.get("output_type") != "stream":
                continue
            text = out.get("text", "")
            if isinstance(text, list):
                text = "".join(text)
            for line in text.splitlines():
                if WARN_LINE.search(line):
                    key = strip_ansi(line.strip())[:250]
                    seen.setdefault(key, abs_idx)
    if seen:
        mesa_lines = [ln for ln in seen if MESA_WARN.search(ln)]
        print(f"\n{len(seen)} unique warning(s) during execution:")
        for line, idx in seen.items():
            tag = "mesa " if MESA_WARN.search(line) else "other"
            print(f"  [{tag}] [cell {idx}] {line}")
        if mesa_lines:
            print(f"{len(mesa_lines)} of these come from mesa. Mesa Deprecation/FutureWarnings "
                  "mean the migration is not finished, even though the notebook runs.")
        else:
            print("None of these come from mesa — library drift (matplotlib/seaborn/pandas), "
                  "out of scope unless it blocks the run. The migration is not implicated.")


def report_first_error(nb) -> bool:
    """Print the first error output found; return True if one was found."""
    code_idx = 0
    for abs_idx, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        code_idx += 1
        for out in cell.get("outputs", []):
            if out.get("output_type") == "error":
                print(f"FAILED at code cell #{code_idx} (cell index {abs_idx})")
                print(f"{out.get('ename')}: {strip_ansi(out.get('evalue', ''))}")
                print("--- cell source ---")
                print(excerpt(cell.source))
                tb = [strip_ansi(line) for line in out.get("traceback", [])]
                if tb:
                    print("--- traceback (tail) ---")
                    print("\n".join(tb[-12:]))
                return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook")
    parser.add_argument("--timeout", type=int, default=120,
                        help="per-cell timeout in seconds (default 120)")
    args = parser.parse_args()

    # Surface library DeprecationWarnings (hidden by default in IPython) so an
    # apparently-green notebook still reveals unfinished migration work.
    # The narrow ignore filters one piece of environmental noise: on macOS /
    # CPython 3.12+, any %pip cell's subprocess spawn emits a stdlib pty.py
    # forkpty DeprecationWarning that has nothing to do with the notebook.
    # Mesa Future/DeprecationWarnings still surface (module-scoped filter;
    # verified with a deliberate mesa.Model(seed=...) counter-probe).
    os.environ.setdefault("PYTHONWARNINGS",
                          "default,ignore::DeprecationWarning:pty")

    path = Path(args.notebook)
    try:
        nb = nbformat.read(path, as_version=4)
    except Exception as exc:  # noqa: BLE001
        print(f"Could not read notebook: {exc}")
        return 2

    client = NotebookClient(
        nb,
        timeout=args.timeout,
        kernel_name="python3",
        resources={"metadata": {"path": str(path.parent.resolve())}},
        allow_errors=False,
    )
    status = 0
    try:
        client.execute()
        print(f"OK: all cells executed ({path.name})")
        report_warnings(nb)
    except CellTimeoutError as exc:
        status = 1
        print(f"TIMEOUT after {args.timeout}s per cell.")
        print(strip_ansi(str(exc))[:2000])
        print("Hint: a cell that blocks forever is often an old ModularServer "
              "launch or an unbounded run loop — migrate or bound it.")
    except DeadKernelError as exc:
        status = 1
        print(f"KERNEL DIED: {strip_ansi(str(exc))[:500]}")
        print("Hint: not a Python exception in a cell — usually OOM or a native-"
              "library crash. Rerun the offending cell's code in a plain script "
              "to isolate it.")
    except CellExecutionError:
        status = 1
        # Details live in the cell outputs; printed below.
    except Exception as exc:  # noqa: BLE001
        status = 1
        print(f"Execution aborted: {type(exc).__name__}: {strip_ansi(str(exc))[:2000]}")
    finally:
        nbformat.write(nb, path)

    if status != 0 and not report_first_error(nb):
        print("(No error output captured in the notebook; see message above.)")
    return status


if __name__ == "__main__":
    sys.exit(main())
