"""The page is built from three static files with no framework and no build
step, so nothing catches a renamed element: app.js would throw on the first
frame and the garden would render as an empty readout."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
HTML = (SITE / "index.html").read_text(encoding="utf-8")
APP = (SITE / "assets" / "app.js").read_text(encoding="utf-8")


def html_ids() -> set[str]:
    return set(re.findall(r'id="([^"]+)"', HTML))


def test_app_only_touches_ids_that_exist():
    wanted = set(re.findall(r"getElementById\('([^']+)'\)", APP))
    assert wanted, "app.js stopped using getElementById"
    missing = wanted - html_ids()
    assert not missing, f"app.js looks for elements index.html does not have: {missing}"


def test_app_does_not_query_selectors_that_could_miss():
    """Every selector app.js uses must be anchored to an id or a class
    index.html actually declares, so a markup rename cannot silently
    detach the timeline from the data."""
    classes = set(re.findall(r'class="([^"]+)"', HTML))
    html_classes = {c for group in classes for c in group.split()}
    used = set(re.findall(r"querySelector(?:All)?\('([^']+)'\)", APP))
    for sel in used:
        if sel.startswith("#"):
            assert sel[1:] in html_ids(), f"missing id for selector {sel}"
        elif sel.startswith("."):
            assert sel[1:] in html_classes, f"missing class for selector {sel}"


def test_payload_loads_before_the_code_that_reads_it():
    """garden.js must be parsed before flower.js and app.js run, or
    window.GARDEN is undefined and nothing draws."""
    order = [HTML.index(f'src="{s}"')
             for s in ("data/garden.js", "assets/flower.js", "assets/app.js")]
    assert order == sorted(order), "scripts are loaded out of order"


def test_every_readout_the_page_shows_is_wired_up():
    """Each readout span in the HTML is assigned by app.js — a label with a
    permanent em-dash would look like a bug to a visitor."""
    readouts = {i for i in html_ids() if i.startswith("ro-")}
    assert len(readouts) >= 4, "the masthead readouts disappeared"
    for rid in readouts:
        assert f"'{rid}'" in APP, f"nothing ever writes #{rid}"
