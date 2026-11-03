"""Tests for the shipped site: the committed payload, the HTML, and the
README must all agree with the source CSVs.

CI additionally re-exports garden.js byte-for-byte; here we check the
semantic contract — what the page reads is exactly what the pipeline
computes, and every asset any document references actually exists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.pipeline import (decorate, garden_totals, load_events,
                          load_prices, web_payload)

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
README = ROOT / "README.md"

# window.GARDEN = {...};   (possibly with trailing semicolon/newline)
PAYLOAD_RE = re.compile(r"^\s*window\.GARDEN\s*=\s*(\{.*\})\s*;?\s*$", re.S)


@pytest.fixture(scope="module")
def on_disk() -> dict:
    text = (SITE / "data" / "garden.js").read_text(encoding="utf-8")
    m = PAYLOAD_RE.match(text)
    assert m, "site/data/garden.js must assign window.GARDEN"
    return json.loads(m.group(1))


@pytest.fixture(scope="module")
def fresh() -> dict:
    df = decorate(load_prices())
    tot = garden_totals(df)
    return web_payload(df, tot, load_events())


# --------------------------------------------------------------------------- #
# the payload the browser reads                                                #
# --------------------------------------------------------------------------- #

def test_payload_matches_a_fresh_pipeline_run(on_disk, fresh):
    """The committed garden.js must equal what the CSVs produce today."""
    assert on_disk == fresh


def test_payload_marks_the_data_cutoff(on_disk):
    assert on_disk["generated"] == "2026-10"
    assert on_disk["months"][-1] == "2026-10"
    assert len(on_disk["months"]) == 70


def test_payload_carries_everything_the_page_needs(on_disk):
    for sym in ("punks", "bayc", "azuki", "doodles", "moonbirds"):
        s = on_disk["series"][sym]
        assert len(s["floor_eth"]) == 70
        assert len(s["drawdown"]) == 70
    assert len(on_disk["totals"]["market_usd"]) == 70
    assert len(on_disk["eth_usd"]) == 70
    assert len(on_disk["events"]) == 17
    assert len(on_disk["collections"]) == 5


def test_payload_is_valid_javascript(on_disk):
    """Guard the wrapper, not just the JSON: one stray brace kills the page."""
    text = (SITE / "data" / "garden.js").read_text(encoding="utf-8")
    assert text.startswith("window.GARDEN")
    # re-serialising must round-trip through JSON again
    assert json.loads(json.dumps(on_disk)) == on_disk


# --------------------------------------------------------------------------- #
# index.html                                                                   #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def html() -> str:
    return (SITE / "index.html").read_text(encoding="utf-8")


def test_html_references_only_existing_assets(html):
    refs = re.findall(r'(?:src|href)="([^"]+)"', html)
    local = [r for r in refs if not r.startswith(("http", "data:", "#"))]
    assert local, "expected local asset references"
    for ref in local:
        assert (SITE / ref.split("#")[0]).exists(), f"broken ref: {ref}"


def test_html_has_the_accessibility_basics(html):
    assert '<html lang="en">' in html
    assert 'name="description"' in html
    assert "<title>" in html
    # the canvas is decorative — the readouts carry the data for screen readers
    assert 'id="ro-month"' in html and 'id="ro-value"' in html


def test_html_loads_the_three_scripts_and_stylesheet(html):
    for asset in ("assets/style.css", "assets/flower.js", "assets/app.js",
                  "data/garden.js"):
        assert f'"{asset}"' in html, f"index.html does not load {asset}"


def test_og_image_is_absolute_so_social_previews_work(html):
    m = re.search(r'property="og:image" content="([^"]+)"', html)
    assert m, "og:image missing"
    assert m.group(1).startswith("https://"), (
        "og:image must be an absolute URL or link previews show nothing"
    )


# --------------------------------------------------------------------------- #
# README                                                                       #
# --------------------------------------------------------------------------- #

def test_readme_local_links_and_images_exist():
    text = README.read_text(encoding="utf-8")
    refs = set(re.findall(r'(?:src|href)="([^"]+)"', text))
    refs |= set(re.findall(r"\]\(([^)#\s]+)\)", text))
    local = {r for r in refs if not r.startswith(("http", "#"))}
    assert len(local) >= 10, "README should showcase many artifacts"
    for ref in local:
        assert (ROOT / ref).exists(), f"README points at missing file: {ref}"


def test_readme_shows_the_live_site_and_the_badges():
    text = README.read_text(encoding="utf-8")
    assert "maanas-pab.github.io/nft-graveyard-economics" in text
    assert "actions/workflows/ci.yml/badge.svg" in text
    assert "garden-anim.gif" in text
