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


def test_check_reproduces_what_ci_does():
    """`make check` must be the local mirror of the CI job, or the two drift.

    The suite arrives through the `test` prerequisite; the recipe itself
    rebuilds the payload and diffs it against the committed artifact.
    """
    text = MAKEFILE.read_text(encoding="utf-8")
    block = re.search(r"^check:(.*?)^(?=[a-z][a-z0-9_-]*:|\Z)", text, re.M | re.S)
    assert block, "no check target"
    head, _, body = block.group(0).partition("\n")
    assert "test" in head.split(":")[1].split(), "check must depend on the test target"
    assert "src.pipeline --web" in body, "check does not rebuild the payload"
    assert "git diff" in body, "check does not compare the rebuilt payload"
    assert "garden.js" in body, "check does not gate on the site payload"
