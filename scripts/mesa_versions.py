#!/usr/bin/env python3
"""Version parsing and lifecycle-status computation shared by the skill's scripts.

PEP-440-lite: handles every version string Mesa has ever published
('0.8.7.1', '2.1', '3.0.0a0', '3.5.0b0', '2.3.0.dev0', '2.3.0rc1', '4.0.0a0')
plus git tags ('v3.5.1'). Raises ValueError on anything else — prose like
'3.1 (deprecated 3.0)' must never silently parse into garbage.

Ordering: '3.5.0b0' < '3.5.0'; '2.1' == '2.1.0'; '0.8.7' < '0.8.7.1'.

Stdlib only. Python 3.9+.
"""
import re

# Pre-release rank: dev < alpha < beta < rc < final.
_PRE = {"dev": 0, "a": 1, "alpha": 1, "b": 2, "beta": 2, "rc": 3, "c": 3}
_FINAL = (9, 0)  # tail that sorts a final release above any of its pre-releases

_VERSION_RX = re.compile(
    r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?"
    r"(?:[.\-]?(dev|alpha|beta|rc|a|b|c)\.?(\d*))?",
    re.IGNORECASE,
)


def parse_version(v):
    """'3.5.0b0' -> (3, 5, 0, 0, 2, 0). Raises ValueError on unparseable input."""
    if not isinstance(v, str):
        raise ValueError(f"version must be a string, got {type(v).__name__}: {v!r}")
    m = _VERSION_RX.fullmatch(v.strip().lower())
    if not m:
        raise ValueError(f"unparseable version: {v!r}")
    nums = tuple(int(g or 0) for g in m.group(1, 2, 3, 4))
    pre = m.group(5)
    tail = _FINAL if pre is None else (_PRE[pre], int(m.group(6) or 0))
    return nums + tail


LIFECYCLE_FIELDS = ("introduced", "deprecated", "superseded", "removed",
                    "applicable_min", "applicable_max")


def validate_lifecycle(entry):
    """Parse every lifecycle field of a registry entry; raise on prose/garbage."""
    for field in LIFECYCLE_FIELDS:
        value = entry.get(field)
        if value is None:
            continue
        try:
            parse_version(value)
        except ValueError as exc:
            raise ValueError(
                f"registry entry {entry.get('id', '?')!r}: field {field!r}: {exc}"
            ) from exc
    for band in entry.get("by_target") or []:
        for field in ("min", "max"):
            value = band.get(field)
            if value is None:
                continue
            try:
                parse_version(value)
            except ValueError as exc:
                raise ValueError(
                    f"registry entry {entry.get('id', '?')!r}: by_target {field!r}: {exc}"
                ) from exc


def status_at(entry, target):
    """Lifecycle status of a registry entry at the parsed target version tuple.

    Precedence: not-yet-introduced (the API does not exist at the target)
    beats removed beats deprecated beats legacy beats current.
    """
    intro = entry.get("introduced")
    if intro and target < parse_version(intro):
        return "not-yet-introduced"
    removed = entry.get("removed")
    if removed and target >= parse_version(removed):
        return "removed"
    deprecated = entry.get("deprecated")
    if deprecated and target >= parse_version(deprecated):
        return "deprecated"
    superseded = entry.get("superseded")
    if superseded and target >= parse_version(superseded):
        return "legacy"
    return "current"


def in_applicable_range(entry, target):
    """False when the entry's concern does not exist at the target at all."""
    lo = entry.get("applicable_min")
    if lo and target < parse_version(lo):
        return False
    hi = entry.get("applicable_max")
    if hi and target >= parse_version(hi):
        return False
    return True


def pick_by_target(bands, target):
    """First by_target band whose [min, max) contains target (min incl., max excl.)."""
    for band in bands or []:
        lo = band.get("min")
        if lo and target < parse_version(lo):
            continue
        hi = band.get("max")
        if hi and target >= parse_version(hi):
            continue
        return band
    return None


def _selftest():
    pv = parse_version
    assert pv("3.5.0b0") < pv("3.5.0")
    assert pv("4.0.0a0") < pv("4.0.0")
    assert pv("2.1") == pv("2.1.0")
    assert pv("0.8.7") < pv("0.8.7.1") < pv("0.8.8")
    assert pv("2.3.0.dev0") < pv("2.3.0rc1") < pv("2.3.0")
    assert pv("v3.5.1") == pv("3.5.1")
    assert pv("3.1.0.dev0") < pv("3.1.0")
    for bad in ("3.1 (deprecated 3.0)", "", "latest", "3.x"):
        try:
            pv(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"should have raised: {bad!r}")
    e = {"id": "t", "introduced": "3.3.0", "deprecated": "3.5.0", "removed": "4.0.0a0"}
    assert status_at(e, pv("3.2.0")) == "not-yet-introduced"
    assert status_at(e, pv("3.3.0")) == "current"
    assert status_at(e, pv("3.4.2")) == "current"
    assert status_at(e, pv("3.5.0")) == "deprecated"
    assert status_at(e, pv("3.5.1")) == "deprecated"
    assert status_at(e, pv("4.0.0a0")) == "removed"
    e2 = {"id": "t2", "superseded": "3.2.0", "removed": "4.0.0a0"}
    assert status_at(e2, pv("2.4.0")) == "current"
    assert status_at(e2, pv("3.2.0")) == "legacy"
    assert status_at(e2, pv("3.5.1")) == "legacy"
    band = pick_by_target([{"max": "3.0.0", "note": "old"},
                           {"min": "3.0.0", "note": "new"}], pv("2.3.4"))
    assert band["note"] == "old"
    band = pick_by_target([{"max": "3.0.0"}, {"min": "3.0.0", "note": "new"}], pv("3.0.0"))
    assert band["note"] == "new"
    print("mesa_versions selftest OK")


if __name__ == "__main__":
    _selftest()
