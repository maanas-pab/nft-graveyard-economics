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
            if root in sys.stdlib_module_names or root in FIRST_PARTY:
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
