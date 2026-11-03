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
    return section(PY, "def bloom_for", "def _shade")


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
