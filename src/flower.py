"""Parametric NFT flower — one species per collection, one bloom per price.

The economics-to-botany mapping (see README for the full table):

    floor / running ATH   ->  bloom radius        (log-scaled, so the eye can read it)
    floor / running ATH   ->  droop angle         (gravity takes the petals)
    floor / running ATH   ->  petal shed count    (petals fall and stay on the soil)
    floor / running ATH   ->  saturation/value    (colour drains out of the bloom)
    floor / running ATH   ->  stem length & lean   (the stalk collapses toward the ground)
    floor / running ATH   ->  coin radius         (the centre disk shrinks to a husk)

Everything is deterministic for a given (price state, seed) so the same month
renders identically in plates, GIFs and previews.
"""

from __future__ import annotations

import colorsys
import math
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PAPER = (246, 241, 231, 255)
SS = 3  # supersampling factor: draw big, LANCZOS down, get free antialiasing

_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Didot.ttc",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/System/Library/Fonts/Times New Roman.ttf",
)


def serif_font(size: int) -> ImageFont.FreeTypeFont:
    """A display serif for plate captions, with graceful fallback."""
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


# --------------------------------------------------------------------------- #
# species                                                                      #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Species:
    petals: int
    shape: str          # round | pointed | blocky
    accent: tuple       # (r, g, b) at full health
    genus: str

    @classmethod
    def from_row(cls, row) -> "Species":
        hexv = row["accent_hex"].lstrip("#")
        accent = tuple(int(hexv[i:i + 2], 16) for i in (0, 2, 4))
        return cls(int(row["petals"]), row["petal_shape"], accent, row["genus"])


# --------------------------------------------------------------------------- #
# the bloom state: what the price says to the flower                           #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Bloom:
    ratio: float        # floor / running ATH, 0..1
    size: float         # head radius as a fraction of cell width
    droop: float        # 0 = proud, 1 = collapsed
    shed: int           # petals that have fallen off
    saturation: float   # 0..1
    value: float        # 0..1
    head_xy: tuple      # where the head sits in the cell
    lean: float         # horizontal drift of the head as the stem fails

    @property
    def alive(self) -> bool:
        return self.ratio > 0.15


def bloom_for(price: float, ath: float, cell: tuple, seed: int = 0) -> Bloom:
    """Translate one price observation into a botanical state.

    Uses a log scale for radius because a floor of 130 ETH and a floor of
    3 ETH differ by 43x, not by the 4x a linear mapping would show.
    """
    ratio = min(1.0, max(0.0, price / ath)) if ath > 0 else 0.0
    log_span = math.log1p(ath) if ath > 0 else 1.0
    size = 0.085 + 0.115 * (math.log1p(max(0.0, price)) / log_span)

    droop = (1.0 - ratio) ** 1.15
    shed_frac = max(0.0, (0.55 - ratio) / 0.55) ** 1.4      # shed only once bad
    return Bloom(
        ratio=ratio,
        size=size,
        droop=droop,
        shed=shed_frac,
        saturation=0.18 + 0.82 * ratio ** 0.65,
        value=0.30 + 0.70 * ratio ** 0.55,
        head_xy=None,  # resolved in render from cell + lean
        lean=droop * (0.16 if seed % 2 else -0.16),
    )


# --------------------------------------------------------------------------- #
# colour                                                                       #
# --------------------------------------------------------------------------- #

DEAD_LEAF = (122, 104, 78)
GREEN_LIVE = (94, 126, 74)
GREEN_DEAD = (116, 102, 76)


def _shade(rgb, sat: float, val: float, decay: float) -> tuple:
    """Desaturate + darken + rot toward dead-leaf brown. Pure colour math."""
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    s *= sat
    l = l * (0.35 + 0.65 * val)
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    out = [int(c * 255) for c in (r, g, b)]
    return tuple(int(o + (d - o) * decay) for o, d in zip(out, DEAD_LEAF))


def _mix(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


# --------------------------------------------------------------------------- #
# geometry                                                                     #
# --------------------------------------------------------------------------- #

def _petal_poly(length, width, shape, samples=22):
    """Petal in local space: base at origin, tip up the +y axis, gravity +y down.

    Returns a closed polygon plus the spine points (for veins / gravity).
    """
    left, right, spine = [], [], []
    for i in range(samples + 1):
        t = i / samples
        if shape == "round":
            w = width * math.sin(math.pi * t ** 0.78) ** 0.9
        elif shape == "pointed":
            w = width * math.sin(math.pi * t) ** 1.55
        elif shape == "blocky":                     # pixel-art petal: stair steps
            steps = 4
            level = round(t * steps) / steps
            w = width * (0.98 if level < 0.78 else (0.6 if level < 1.0 else 0.0))
        else:
            w = width * math.sin(math.pi * t)
        y = length * t
        spine.append((0.0, y))
        left.append((-w, y))
        right.append((w, y))
    return left + right[::-1], spine


def _rot(pts, ang):
    c, s = math.cos(ang), math.sin(ang)
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


# --------------------------------------------------------------------------- #
# rendering                                                                    #
# --------------------------------------------------------------------------- #

def render_flower(cell=(420, 560), species: Species = None, bloom: Bloom = None,
                  seed: int = 0, epitaph: str | None = None,
                  background=None) -> Image.Image:
    """Draw one flower as an RGBA image at `cell`, supersampled SSx then reduced."""
    w, h = cell[0] * SS, cell[1] * SS
    img = Image.new("RGBA", (w, h), background or (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rnd = random.Random(seed)

    ground_y = int(h * 0.845)
    cx = w * (0.5 + bloom.lean)
    cy = h * (0.30 + 0.26 * bloom.droop)          # the head sinks as price dies
    R = bloom.size * w

    decay = 1.0 - bloom.ratio                      # 0 at ATH, 1 at zero
    petal_c = _shade(species.accent, bloom.saturation, bloom.value, decay * 0.72)
    petal_hi = _mix(petal_c, (255, 250, 240), 0.30)
    petal_lo = _mix(petal_c, (0, 0, 0), 0.28)
    stem_c = _mix(GREEN_LIVE, GREEN_DEAD, decay ** 0.7)

    # --- shadow ------------------------------------------------------------
    sh_r = R * (0.9 - 0.5 * bloom.droop)
    d.ellipse([cx - sh_r, ground_y - sh_r * 0.16, cx + sh_r, ground_y + sh_r * 0.16],
              fill=(60, 45, 30, 46 + int(60 * bloom.ratio)))

    # --- stem: quadratic bezier from soil to head --------------------------
    sx, sy = w * 0.5, ground_y
    bow = (cx - sx) * 0.35 + w * 0.10 * bloom.lean * 4
    ctrl = (sx + bow * 0.4, sy - (sy - cy) * 0.55)
    steps, stem_pts = 40, []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * sx + 2 * (1 - t) * t * ctrl[0] + t ** 2 * cx
        y = (1 - t) ** 2 * sy + 2 * (1 - t) * t * ctrl[1] + t ** 2 * cy
        stem_pts.append((x, y))
    stem_w = max(2, int(w * (0.020 + 0.016 * bloom.ratio)))
    d.line(stem_pts, fill=stem_c + (255,), width=stem_w, joint="curve")
    d.line(stem_pts, fill=_mix(stem_c, (255, 255, 255), 0.22) + (255,),
           width=max(1, stem_w // 3), joint="curve")

    # --- one leaf, drooping with the rest ----------------------------------
    lt = 0.42
    lx, ly = stem_pts[int(lt * steps)]
    leaf_len = R * (1.05 - 0.45 * bloom.droop)
    lpoly, _ = _petal_poly(leaf_len, leaf_len * 0.30, "pointed")
    lpts = _rot(lpoly, math.radians(58 + 42 * bloom.droop))
    lpts = [(lx + x, ly + y + bloom.droop * leaf_len * 0.55 * (abs(y) / leaf_len) ** 2)
            for x, y in lpts]
    d.polygon(lpts, fill=_mix(stem_c, (200, 220, 160), 0.35) + (255,))

    # --- petals: outer ring, then inner ring; shed ones lie on the soil -----
    n = species.petals
    total = 2 * n
    shed_n = round(total * bloom.shed)
    step = math.ceil(total / shed_n) if shed_n else total + 1
    # deterministic shed pattern: every `step`-th petal drops, no RNG required
    shed = {(k % n, k // n) for k in range(0, total, step)} if shed_n else set()

    angle0 = rnd.uniform(0, math.tau)
    for ring, (scale, ring_off, depth) in enumerate(
            ((1.0, 0.0, 0.0), (0.62, math.pi / n, 0.18))):
        for i in range(n):
            ang = angle0 + ring_off + i * math.tau / n   # screen direction of tip
            length = R * scale * (0.86 + 0.22 * bloom.ratio)
            width = length * (0.42 if species.shape != "pointed" else 0.34)
            poly, _ = _petal_poly(length, width, species.shape)
            # local base is at the origin, tip at +y — rotate so the tip faces
            # outward along `ang`, then translate to the head centre.
            local = _rot(poly, ang - math.pi / 2)
            local = [(x, y + bloom.droop * R * 1.35 * (y / length) ** 2)
                     for x, y in local]                     # gravity, in screen space
            pts = [(cx + x, cy + y) for x, y in local]

            fill = _mix(petal_lo if ring == 0 else petal_c, petal_hi,
                        0.18 + 0.5 * ((i * 37 + ring * 11) % 7) / 7)
            fill = _mix(fill, DEAD_LEAF, depth + decay * 0.25)

            if (i, ring) in shed:                           # re-lay it on the soil
                fx = sx + rnd.uniform(-0.42, 0.42) * w * (0.4 + 0.6 * bloom.ratio)
                fy = ground_y + rnd.uniform(-0.012, 0.045) * h
                flat = _rot(poly, rnd.uniform(-math.pi, math.pi))
                # fallen petals lie flat: squash against the ground plane
                flat = [(fx + x * 1.25, fy + y * 0.40) for x, y in flat]
                dead = _mix(fill, DEAD_LEAF, 0.72)
                d.polygon(flat, fill=dead + (255,),
                          outline=_mix(dead, (60, 50, 35), 0.5) + (255,))
                continue

            d.polygon(pts, fill=fill + (255,),
                      outline=_mix(fill, (70, 55, 40), 0.45) + (255,))

    # --- the coin: centre disk shrinks and rusts ---------------------------
    coin_r = R * (0.10 + 0.30 * bloom.ratio)
    coin = _mix((214, 176, 66), (118, 96, 62), decay ** 0.8)
    d.ellipse([cx - coin_r, cy - coin_r, cx + coin_r, cy + coin_r],
              fill=coin + (255,), outline=_mix(coin, (70, 55, 30), 0.5) + (255,),
              width=max(1, int(1.5 * SS)))
    for k in range(10):                                        # stipple seeds
        a = k * math.tau / 10 + 0.3
        rr = coin_r * 0.55
        px, py = cx + rr * math.cos(a), cy + rr * math.sin(a)
        r0 = max(1, int(coin_r * 0.09))
        d.ellipse([px - r0, py - r0, px + r0, py + r0],
                  fill=_mix(coin, (60, 45, 25), 0.55) + (255,))

    # --- headstone for the fully departed ----------------------------------
    if epitaph:
        st_w, st_h = w * 0.30, h * 0.14
        bx = w * 0.5 - st_w / 2
        by = ground_y - st_h
        stone = (168, 163, 154, 255)
        d.rounded_rectangle([bx, by, bx + st_w, ground_y + st_h * 0.18],
                            radius=st_w * 0.30, fill=stone,
                            outline=(110, 106, 99, 255), width=int(1.5 * SS))
        f = serif_font(int(st_h * 0.30))
        d.text((bx + st_w / 2, by + st_h * 0.45), epitaph, font=f,
               fill=(70, 66, 60, 255), anchor="mm")

    return img.resize(cell, Image.LANCZOS)


def paper(cell=(420, 560), tone=PAPER) -> Image.Image:
    """Warm laid-paper backdrop with a faint vignette, for specimen plates."""
    w, h = cell[0] * SS, cell[1] * SS
    img = Image.new("RGBA", (w, h), tone)
    d = ImageDraw.Draw(img)
    for i in range(26):                                        # vignette rings
        t = i / 26
        a = int(16 * t)
        d.rectangle([-w * 0.3 * t, -h * 0.3 * t, w * (1 + 0.3 * t), h * (1 + 0.3 * t)],
                    outline=(120, 100, 70, a))
    return img.resize(cell, Image.LANCZOS)
