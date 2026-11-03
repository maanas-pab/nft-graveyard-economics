"""The Makefile is the documented interface: what the header promises must
exist, and what exists must be declared phony (so a stray file named
`site` or `test` can never shadow a target)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = ROOT / "Makefile"

PUBLIC_TARGETS = {
    "all", "data", "flowers", "charts", "gif", "site",
    "test", "check", "serve", "clean",
}


def targets() -> set[str]:
    text = MAKEFILE.read_text(encoding="utf-8")
    return set(re.findall(r"^([a-z][a-z0-9_-]*):(?:\s|$)", text, re.M))


def documented() -> set[str]:
    text = MAKEFILE.read_text(encoding="utf-8")
    return set(re.findall(r"^#\s+make (\S+)", text, re.M))


def test_every_documented_target_exists():
    missing = documented() - targets()
    assert not missing, f"header documents targets that do not exist: {missing}"


def test_every_public_target_is_declared():
    text = MAKEFILE.read_text(encoding="utf-8")
    m = re.search(r"^\.PHONY:\s*(.+)$", text, re.M)
    assert m, "Makefile has no .PHONY line"
    phony = set(m.group(1).split())
    missing = PUBLIC_TARGETS - phony
    assert not missing, f"targets not in .PHONY: {missing}"
    assert PUBLIC_TARGETS <= targets(), "a public target is missing its recipe"
