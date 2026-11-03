"""Repository hygiene: the declared dependencies must cover what the code
imports, or a fresh clone fails at `pip install -r requirements.txt`."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"
SOURCES = sorted((ROOT / "src").glob("*.py")) + sorted((ROOT / "tests").glob("*.py"))

FIRST_PARTY = {"src"}

# sys.stdlib_module_names exists from 3.10; fall back to the names this
# codebase actually reaches for so the test also runs on older local pythons.
STDLIB = getattr(sys, "stdlib_module_names", None) or {
    "__future__", "argparse", "colorsys", "dataclasses", "datetime", "json",
    "math", "pathlib", "random", "re", "subprocess", "sys",
}
# importable module name -> the name it is declared under in requirements.txt
MODULE_TO_REQUIREMENT = {
    "pandas": "pandas",
    "PIL": "Pillow",
    "matplotlib": "matplotlib",
    "pytest": "pytest",
    "yaml": "pyyaml",
}


def third_party_imports() -> set[str]:
    found = set()
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for mod in re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][\w.]*)", text, re.M):
            root = mod.split(".")[0]
            if root in STDLIB or root in FIRST_PARTY:
                continue
            found.add(root)
    return found


def test_requirements_covers_every_third_party_import():
    imports = third_party_imports()
    assert imports, "no imports found — the scanner is broken"
    reqs = REQUIREMENTS.read_text(encoding="utf-8")
    for mod in sorted(imports):
        assert mod in MODULE_TO_REQUIREMENT, f"{mod} imported but not mapped to a requirement"
        name = MODULE_TO_REQUIREMENT[mod]
        assert re.search(rf"^{re.escape(name)}[<>=]", reqs, re.M | re.I), (
            f"{mod} is imported but {name} is not in requirements.txt"
        )


def test_requirements_has_no_duplicates():
    names = [m.group(1) for m in
             re.finditer(r"^([A-Za-z][\w-]*)[<>=]", REQUIREMENTS.read_text(), re.M)]
    assert len(names) == len(set(names)), f"duplicate requirement: {names}"


def test_license_is_present_and_advertised():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in license_text
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "MIT" in readme and "](LICENSE)" in readme, "README does not link the license"


def test_provenance_notes_are_shipped():
    """The dataset is hand-compiled; the caveats must travel with it."""
    notes = ROOT / "data" / "README.md"
    assert notes.exists(), "data/README.md (provenance) is missing"
    text = notes.read_text(encoding="utf-8").lower()
    for word in ("provenance", "caveat", "approx"):
        assert word in text, f"provenance notes never mention {word}"


def tracked_files() -> list[str]:
    import subprocess
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [l for l in out.stdout.splitlines() if l]


def test_no_merge_conflict_markers_are_committed():
    bad = []
    for name in tracked_files():
        path = ROOT / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if re.search(r"^(<<<<<<<|>>>>>>>|=======) ", text, re.M):
            bad.append(name)
    assert not bad, f"conflict markers committed in: {bad}"


def test_no_junk_is_tracked():
    """Caches, virtualenvs and OS droppings stay out of the index."""
    junk = [n for n in tracked_files()
            if n.startswith((".github/../",)) is False and (
                n.endswith(".DS_Store") or "/__pycache__/" in n
                or n.startswith(".pytest_cache") or n.startswith(".venv"))]
    assert not junk, f"junk tracked by git: {junk}"

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("__pycache__/", ".venv/", ".pytest_cache/", ".DS_Store",
                    "build/scratch/"):
        assert pattern in gitignore, f".gitignore no longer covers {pattern}"
