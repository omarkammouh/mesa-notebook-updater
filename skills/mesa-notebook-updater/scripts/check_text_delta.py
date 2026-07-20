#!/usr/bin/env python3
"""Audit the TEACHING-TEXT diff of a migration against the skill's text contract.

Given the pre-edit ORIGINAL and the MIGRATED notebook (or .py), it aligns the
prose (markdown cells + code comments/docstrings) and flags every way the edit
could have broken "minimal delta, zero staleness, author's voice, no migration
residue, no translation":

    ADDED-MARKDOWN    a markdown cell exists only in the migrated file
                      (a new explanation — minimal-delta forbids adding prose)
    REMOVED-MARKDOWN  a markdown cell was deleted
    CELL-COUNT        the cell count changed (structure must be preserved)
    RESIDUE           a migration-commentary phrase was INTRODUCED ("used to be",
                      "updated for Mesa", "voorheen", ...) — never allowed
    RESIDUAL-STALE    a removed/legacy API NAME still sits in the migrated prose
                      (registry prose patterns) — staleness the edit missed
    SENTENCE-DELTA    a changed cell's sentence count moved by >1 (rewrite too big
                      for minimal delta)
    LANGUAGE-SHIFT    a changed cell's dominant natural language flipped — a
                      likely translation (notebooks may be written in any language;
                      never translate — keep it exactly as the author wrote it)
    CHANGED           a cell changed within tolerance — surfaced for the reader
                      gate (confirm the change is behavior-tied and in the voice)

This is the machine half of the finishing gate; the reader gate (a human or an
adversarial-reader pass) still judges *voice* on the CHANGED cells it surfaces.

Usage:  check_text_delta.py ORIGINAL.ipynb MIGRATED.ipynb [--json] [--registry P]
        (get ORIGINAL from git: `git show HEAD:path > /tmp/orig.ipynb`)

Exit: 0 = no hard flags; 1 = hard flags to resolve; 2 = bad input.
Stdlib only. Python 3.9+.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_REGISTRY = HERE.parent / "references" / "api-registry.json"

# Migration-commentary phrases that must never be introduced (EN + NL).
RESIDUE = [
    r"updated for mesa", r"migrated to", r"\bused to be\b", r"in the new version",
    r"in newer versions?", r"as of mesa", r"changed from", r"instead of the old",
    r"this now uses", r"we now use", r"\bformerly\b", r"no longer needs?",
    r"replaced by", r"in older versions?", r"the old (?:api|way|scheduler)",
    # Dutch
    r"\bvoorheen\b", r"\bvroeger\b", r"bijgewerkt", r"verouderd",
    r"vervangen door", r"in de nieuwe versie", r"niet langer nodig",
    r"gewijzigd van", r"de oude (?:api|manier|scheduler)",
]
RESIDUE_RX = [re.compile(p, re.IGNORECASE) for p in RESIDUE]

# Function-word sets for a language-agnostic "was this translated?" heuristic.
# The contract is "never translate" — so we guess the dominant natural language of
# a cell before and after and flag a flip. Add a language here to cover it; the sets
# only need to be distinctive, not exhaustive. Code tokens (in backticks) are noise
# and mostly wash out. English is the API/lingua-franca baseline.
LANG_WORDS = {
    "en": {"the", "a", "an", "and", "of", "to", "in", "is", "are", "we", "you",
           "this", "that", "with", "for", "not", "as", "by", "on", "it", "each"},
    "nl": {"de", "het", "een", "en", "van", "is", "op", "met", "die", "dat",
           "voor", "niet", "aan", "als", "we", "wordt", "worden", "elke",
           "naar", "zijn", "deze", "bij", "om", "geen", "maar", "ook", "per"},
    "de": {"der", "die", "das", "und", "von", "zu", "ist", "sind", "wir", "mit",
           "für", "nicht", "auf", "den", "dem", "ein", "eine", "als", "auch", "wird"},
    "fr": {"le", "la", "les", "un", "une", "et", "de", "des", "du", "est", "sont",
           "nous", "avec", "pour", "ne", "pas", "dans", "sur", "que", "qui", "au"},
    "es": {"el", "la", "los", "las", "un", "una", "y", "de", "del", "es", "son",
           "con", "para", "no", "en", "que", "se", "por", "como", "cada"},
    "it": {"il", "la", "le", "un", "una", "e", "di", "del", "che", "sono",
           "con", "per", "non", "in", "su", "come", "si", "nel", "dei"},
    "pt": {"o", "a", "os", "as", "um", "uma", "e", "de", "do", "da", "que",
           "sao", "com", "para", "nao", "em", "no", "na", "se", "cada"},
}

HARD = {"ADDED-MARKDOWN", "REMOVED-MARKDOWN", "CELL-COUNT", "RESIDUE",
        "RESIDUAL-STALE", "SENTENCE-DELTA", "LANGUAGE-SHIFT"}


def load_cells(path: Path):
    """Return list of (id_or_None, cell_type, source_text)."""
    if path.suffix == ".ipynb":
        nb = json.loads(path.read_text(encoding="utf-8"))
        out = []
        for c in nb.get("cells", []):
            src = c.get("source", "")
            if isinstance(src, list):
                src = "".join(src)
            out.append((c.get("id"), c.get("cell_type", "code"), src))
        return out
    return [(None, "code", path.read_text(encoding="utf-8"))]


def sentences(text):
    # markdown-aware-ish: strip code fences, count sentence enders
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", " ", text)
    parts = re.split(r"[.!?]+(?:\s|$)", text.strip())
    return [p for p in parts if p.strip()]


def dominant_lang(text):
    """Best-guess natural language of a prose cell, or None if too short/ambiguous.

    A cheap function-word vote — enough to notice a translation, not a linguistics
    engine. Returns the highest-scoring language whose share clears a floor."""
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    if len(words) < 6:
        return None
    best, best_score = None, 0.0
    for lang, ws in LANG_WORDS.items():
        score = sum(w in ws for w in words) / len(words)
        if score > best_score:
            best, best_score = lang, score
    return best if best_score >= 0.08 else None


def new_residue(old, new):
    """Residue phrases present in NEW but not in OLD (introduced by the edit)."""
    hits = []
    for rx in RESIDUE_RX:
        if rx.search(new) and not rx.search(old):
            hits.append(rx.pattern)
    return hits


def prose_stale_patterns(registry_path):
    """Compiled patterns for a genuinely-DEAD API NAME left in migrated prose.

    Only entries that (a) apply to markdown, (b) carry a removal/deprecation/
    supersession stamp (so the name is actually stale, not merely worth a look),
    and (c) are NOT `judge`. The judge exclusion matters: `stale-version-claim`
    matches any "Mesa X.Y" banner including the *correct* target version, and
    `stale-term-unique-id` matches a legitimate reading of `unique_id` — those are
    human-verify hits, not proof of staleness, so they must not be hard flags
    here. The scanner remains the authority on API-name staleness anywhere;
    this is a delta-scoped convenience double-check."""
    try:
        reg = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    out = []
    for e in reg.get("entries", []):
        if e.get("applies_to") not in ("markdown", "both"):
            continue
        if e.get("judge"):
            continue
        if not (e.get("removed") or e.get("deprecated") or e.get("superseded")):
            continue
        for p in e["patterns"]:
            try:
                out.append((e["id"], re.compile(p)))
            except re.error:
                pass
    return out


def align(orig, migr):
    """Yield ('both'|'added'|'removed', orig_cell_or_None, migr_cell_or_None, key).

    Aligns by cell id when BOTH files carry ids on every cell; otherwise by index.
    """
    o_ids = [c[0] for c in orig]
    m_ids = [c[0] for c in migr]
    by_id = all(o_ids) and all(m_ids) and len(set(o_ids)) == len(o_ids) and len(set(m_ids)) == len(m_ids)
    if by_id:
        om = {c[0]: c for c in orig}
        mm = {c[0]: c for c in migr}
        seen = set()
        for cid, c in mm.items():
            seen.add(cid)
            if cid in om:
                yield "both", om[cid], c, cid
            else:
                yield "added", None, c, cid
        for cid, c in om.items():
            if cid not in seen:
                yield "removed", c, None, cid
    else:
        n = max(len(orig), len(migr))
        for i in range(n):
            o = orig[i] if i < len(orig) else None
            m = migr[i] if i < len(migr) else None
            if o and m:
                yield "both", o, m, i
            elif m:
                yield "added", None, m, i
            else:
                yield "removed", o, None, i


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("migrated")
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    op, mp = Path(args.original), Path(args.migrated)
    for p in (op, mp):
        if not p.exists():
            print(f"No such file: {p}", file=sys.stderr)
            return 2
    orig, migr = load_cells(op), load_cells(mp)
    stale_rx = prose_stale_patterns(args.registry)

    flags = []

    def add(kind, cell, msg, extra=None):
        flags.append({"kind": kind, "cell": cell, "msg": msg, **(extra or {})})

    if len(orig) != len(migr):
        add("CELL-COUNT", None,
            f"cell count changed {len(orig)} -> {len(migr)} (structure must be preserved)")

    for status, o, m, key in align(orig, migr):
        if status == "added":
            if m[1] == "markdown":
                add("ADDED-MARKDOWN", key, f"new markdown cell: {m[2].strip()[:80]!r}")
            continue
        if status == "removed":
            if o[1] == "markdown":
                add("REMOVED-MARKDOWN", key, f"deleted markdown cell: {o[2].strip()[:80]!r}")
            continue
        # both
        otext, mtext = o[2], m[2]
        if otext == mtext:
            continue  # untouched — perfect minimal delta
        # residue introduced anywhere (markdown or code comment)
        for ph in new_residue(otext, mtext):
            add("RESIDUE", key, f"introduced migration-commentary phrase /{ph}/ — remove it")
        # markdown-specific voice/staleness checks
        if m[1] == "markdown":
            so, sn = len(sentences(otext)), len(sentences(mtext))
            if abs(sn - so) > 1:
                add("SENTENCE-DELTA", key,
                    f"{so} -> {sn} sentences (Δ{sn - so:+d} > ±1) — rewrite too large for minimal delta")
            lo, ln = dominant_lang(otext), dominant_lang(mtext)
            if lo and ln and lo != ln:
                add("LANGUAGE-SHIFT", key,
                    f"dominant language {lo} -> {ln} — likely translation (never translate)")
            for aid, rx in stale_rx:
                if rx.search(mtext):
                    add("RESIDUAL-STALE", key,
                        f"stale API/term still in migrated prose (api: {aid})")
                    break
            add("CHANGED", key, "changed within tolerance — READER GATE: confirm the change "
                "is tied to a changed Mesa behavior and reads in the author's voice",
                {"before": otext.strip()[:400], "after": mtext.strip()[:400]})

    hard = [f for f in flags if f["kind"] in HARD]
    soft = [f for f in flags if f["kind"] == "CHANGED"]

    if args.json:
        print(json.dumps({"hard_flag_count": len(hard),
                          "changed_cell_count": len(soft),
                          "flags": flags}, indent=1))
    else:
        print(f"Text-delta audit: {op.name} -> {mp.name}\n")
        for f in flags:
            if f["kind"] == "CHANGED":
                print(f"[{f['kind']:15s}] cell {f['cell']}: {f['msg']}")
                print(f"    before: {f['before']!r}")
                print(f"    after:  {f['after']!r}")
            else:
                print(f"[{f['kind']:15s}] cell {f['cell']}: {f['msg']}")
        print(f"\n{len(hard)} hard flag(s) to resolve; {len(soft)} changed cell(s) for the reader gate.")
        if not hard and not soft:
            print("Clean: every prose cell is byte-identical to the original (ideal minimal delta).")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
