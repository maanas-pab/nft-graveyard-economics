"""README contracts: no emoji, badges that resolve, a contents list that works.

The README is this project's front page. These tests keep it presentable and
stop the badge row or the anchor list from silently rotting.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
REPO = "maanas-pab/nft-graveyard-economics"

# Codepoint ranges that render as emoji. Arrows (2190-21FF), mathematical
# operators and box-drawing are plain text and stay.
EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # pictographs, emoji, flags
    "\u2600-\u27BF"           # misc symbols + dingbats
    "\u2B00-\u2BFF"           # stars, arrows-as-emoji
    "\u2300-\u23FF"           # clocks, media controls
    "\u25A0-\u25FF"           # geometric shapes
    "\uFE0F"                  # variation selector
    "]"
)


def test_readme_carries_no_emoji():
    """Headings and tables read as text; emoji were deliberately removed."""
    hits = EMOJI_RE.findall(README.read_text(encoding="utf-8"))
    assert not hits, f"README still contains emoji: {hits!r}"
