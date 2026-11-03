"""The flower engine exists twice on purpose: Pillow for the printed plates
(`src/flower.py`), canvas for the live garden (`site/assets/flower.js`).

The README promises "same maths, so the picture and the chart can never
disagree". These tests make that promise executable.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = (ROOT / "src" / "flower.py").read_text(encoding="utf-8")
JS = (ROOT / "site" / "assets" / "flower.js").read_text(encoding="utf-8")


def section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i)
    body = text[i:j]
    # drop docstrings/comments so prose numbers never enter the comparison
    body = re.sub(r'""".*?"""', "", body, flags=re.S)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    body = re.sub(r"//[^\n]*", "", body)
    body = re.sub(r"#[^\n]*", "", body)
    return body


def numbers(text: str) -> set[float]:
    return {round(float(n), 6) for n in re.findall(r"\d+(?:\.\d+)?", text)}


def bloom_py() -> str:
    # bounded at DEAD_LEAF: the module palette sits between bloom_for and
    # _shade, and those RGB triplets are compared separately.
    return section(PY, "def bloom_for", "DEAD_LEAF")


def bloom_js() -> str:
    return section(JS, "function bloomFor", "petal in local space")


def test_bloom_math_is_the_same_number_in_both_engines():
    """Every literal in the price -> botany mapping matches, to the digit."""
    py, js = numbers(bloom_py()), numbers(bloom_js())
    assert py == js, (
        f"only in Python: {sorted(py - js)}; only in JS: {sorted(js - py)}"
    )


def test_the_shared_mapping_is_the_documented_formula():
    """The README's `0.085 + 0.115 · ln(1+floor) / ln(1+ATH)` must exist twice."""
    for body in (bloom_py(), bloom_js()):
        assert "0.085" in body and "0.115" in body
        assert "1.15" in body, "droop exponent missing"
        assert "0.55" in body, "petal-shed threshold missing"
        assert "0.65" in body and "0.55" in body, "saturation/value exponents"


def _rgb(text: str, name: str) -> tuple[int, ...]:
    m = re.search(rf"{name}\s*=\s*[\(\[]\s*([0-9,\s]+?)\s*[\)\]]", text)
    assert m, f"{name} not found"
    return tuple(int(v) for v in m.group(1).split(","))


def test_shared_palette_is_identical():
    for name in ("DEAD_LEAF", "GREEN_LIVE", "GREEN_DEAD"):
        assert _rgb(PY, name) == _rgb(JS, name), f"{name} differs between engines"


def test_ground_line_sits_at_the_same_height():
    """Both renderers put the soil at 84.5% of the cell — or the stems float."""
    py_render = PY[PY.index("def render_flower"):]
    assert "0.845" in py_render, "python engine moved the soil"
    assert "0.845" in JS, "canvas engine moved the soil"
