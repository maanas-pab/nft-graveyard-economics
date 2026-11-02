"""Botanical specimen plates: the same five flowers, frozen at the moments
that mattered. Renders to assets/plates/ for the README and the site.

Three kinds of plate:

    lifecycle_<sym>.png   one collection across its four acts
                          (launch -> peak -> crash -> today)
    garden_<YYYY-MM>.png  all five collections side by side at one date
    lifecycle_grid.png    5 x 4 contact sheet — the whole story in one image
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

from .flower import Species, bloom_for, paper, render_flower, serif_font
from .pipeline import decorate, load_prices

ROOT = Path(__file__).resolve().parent.parent
PLATES = ROOT / "assets" / "plates"

CELL = (300, 420)
INK = (58, 48, 38)
FAINT = (140, 126, 108)
RULE = (188, 174, 150)

# the four acts of every bubble
ACTS = ["launch", "peak", "crash", "today"]


def act_row(g) -> dict:
    """Pick the four dates that tell this collection's story.

    `crash` is the worst print within twelve months of the peak — the violent
    leg down — so it stays distinct from `today`, which is the slow bleed.
    """
    launch = g.iloc[0]
    peak = g.loc[g["floor_eth"].idxmax()]
    last = g.iloc[-1]
    window = g[(g["date"] > peak["date"]) &
               (g["date"] <= peak["date"] + pd.DateOffset(months=12))]
    crash = window.loc[window["floor_eth"].idxmin()] if len(window) else last
    return dict(launch=launch, peak=peak, crash=crash, today=last)


# --------------------------------------------------------------------------- #
# one panel: flower + caption                                                  #
# --------------------------------------------------------------------------- #

def panel(row, species: Species, seed: int, w=CELL[0], h=CELL[1],
          caption_h=84) -> Image.Image:
    """One flower cell plus a caption strip beneath it (date / price / drawdown)."""
    price, ath = float(row["floor_eth"]), float(row["ath_eth"])
    b = bloom_for(price, ath, (w, h), seed=seed)
    epitaph = f"-{abs(row['drawdown_pct']):.0f}%" if row["drawdown_pct"] <= -90 else None

    img = Image.new("RGBA", (w, h + caption_h), (0, 0, 0, 0))
    img.paste(paper((w, h)), (0, 0))
    img.alpha_composite(render_flower((w, h), species, b, seed=seed, epitaph=epitaph))

    d = ImageDraw.Draw(img)
    y0 = h + 10
    d.line([(w * 0.14, y0), (w * 0.86, y0)], fill=RULE + (255,), width=1)
    f_date = serif_font(15)
    f_num = serif_font(21)
    d.text((w / 2, y0 + 20), row["date"].strftime("%b %Y").upper(),
           font=f_date, fill=FAINT + (255,), anchor="mm")
    d.text((w / 2, y0 + 45), f"{price:,.2f} ETH", font=f_num,
           fill=INK + (255,), anchor="mm")
    dd = row["drawdown_pct"]
    col = (150, 46, 38) if dd <= -90 else ((176, 118, 38) if dd <= -50 else FAINT)
    d.text((w / 2, y0 + 68), "—" if abs(dd) < 0.05 else f"{dd:+.1f}%",
           font=f_date, fill=col + (255,), anchor="mm")
    return img


# --------------------------------------------------------------------------- #
# plates                                                                       #
# --------------------------------------------------------------------------- #

def lifecycle_plate(sym: str, meta: pd.DataFrame, df: pd.DataFrame) -> Image.Image:
    """One species, four acts, in a row with a botanical-plate frame."""
    g = df[df["symbol"] == sym].sort_values("date").reset_index(drop=True)
    m = meta[meta["symbol"] == sym].iloc[0]
    acts = act_row(g)
    species = Species.from_row(m)
    seed = sum(ord(c) for c in sym)

    cap = 92
    pad, gap = 56, 26
    w = pad * 2 + CELL[0] * 4 + gap * 3
    header, footer = 196, 104
    h = header + CELL[1] + cap + footer
    img = paper((w, h), tone=(247, 242, 233, 255))
    d = ImageDraw.Draw(img)

    # plate frame
    d.rectangle([18, 18, w - 18, h - 18], outline=RULE + (255,), width=2)
    d.rectangle([26, 26, w - 26, h - 26], outline=RULE + (255,), width=1)

    # title block
    d.text((w / 2, 76), f"{m['genus']} {sym.upper()}",
           font=serif_font(44), fill=INK + (255,), anchor="mm")
    d.text((w / 2, 118), m["collection"],
           font=serif_font(21), fill=FAINT + (255,), anchor="mm")
    d.line([(w * 0.30, 144), (w * 0.70, 144)], fill=RULE + (255,), width=1)

    # four acts
    for i, act in enumerate(ACTS):
        row = acts[act]
        x = pad + i * (CELL[0] + gap)
        p = panel(row, species, seed + i * 7, caption_h=cap)
        img.alpha_composite(p, (x, header))
        d = ImageDraw.Draw(img)
        d.text((x + CELL[0] / 2, header - 24), act.upper(),
               font=serif_font(15), fill=FAINT + (255,), anchor="mm")

    # footer
    d = ImageDraw.Draw(img)
    peak_m = acts["peak"]
    d.text((w / 2, h - 64),
           f"Peak {peak_m['floor_eth']:,.0f} ETH "
           f"({peak_m['date'].strftime('%b %Y')})   ·   "
           f"Floor {acts['today']['floor_eth']:,.2f} ETH   ·   "
           f"{acts['today']['drawdown_pct']:.1f}% from peak",
           font=serif_font(17), fill=INK + (255,), anchor="mm")
    d.text((w / 2, h - 40),
           "GraveNFT Yard — hand-compiled monthly floors, Jan 2021 → Oct 2026",
           font=serif_font(12), fill=FAINT + (255,), anchor="mm")
    return img


def garden_plate(date, meta: pd.DataFrame, df: pd.DataFrame) -> Image.Image:
    """All five species at one moment — the garden as it stood that month."""
    g = df[df["date"] == date]
    cap = 92
    pad, gap = 48, 20
    w = pad * 2 + CELL[0] * 5 + gap * 4
    header, footer = 138, 76
    h = header + CELL[1] + cap + footer
    img = paper((w, h), tone=(247, 242, 233, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([18, 18, w - 18, h - 18], outline=RULE + (255,), width=2)

    stamp = pd.Timestamp(date).strftime("%B %Y")
    total_usd = g["market_usd"].sum()
    d.text((w / 2, 64), f"The Garden — {stamp}",
           font=serif_font(40), fill=INK + (255,), anchor="mm")
    d.text((w / 2, 104),
           f"five blue chips, ${total_usd / 1e6:,.1f}M combined floor value",
           font=serif_font(18), fill=FAINT + (255,), anchor="mm")

    for i, (_, row) in enumerate(g.iterrows()):
        sym = row["symbol"]
        m = meta[meta["symbol"] == sym].iloc[0]
        species = Species.from_row(m)
        seed = sum(ord(c) for c in sym)
        p = panel(row, species, seed, caption_h=cap)
        img.alpha_composite(p, (pad + i * (CELL[0] + gap), header))
    return img


def lifecycle_grid(meta: pd.DataFrame, df: pd.DataFrame) -> Image.Image:
    """5 species x 4 acts contact sheet — the entire narrative in one frame."""
    cap = 92
    pad, gap_x, gap_y = 44, 18, 28
    header, footer = 168, 74
    row_h = CELL[1] + cap
    w = pad * 2 + CELL[0] * 4 + gap_x * 3
    h = header + (row_h + gap_y) * 5 - gap_y + footer
    img = paper((w, h), tone=(247, 242, 233, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([18, 18, w - 18, h - 18], outline=RULE + (255,), width=2)
    d.rectangle([26, 26, w - 26, h - 26], outline=RULE + (255,), width=1)

    d.text((w / 2, 58), "GraveNFT Yard",
           font=serif_font(46), fill=INK + (255,), anchor="mm")
    d.text((w / 2, 102),
           "five blue-chip NFTs, four acts each — launch, peak, crash, today",
           font=serif_font(19), fill=FAINT + (255,), anchor="mm")
    d.line([(w * 0.28, 130), (w * 0.72, 130)], fill=RULE + (255,), width=1)

    # column headers (the four acts)
    for i, act in enumerate(ACTS):
        x = pad + i * (CELL[0] + gap_x)
        d.text((x + CELL[0] / 2, header - 18), act.upper(),
               font=serif_font(15), fill=FAINT + (255,), anchor="mm")

    for r, sym in enumerate(meta["symbol"]):
        g = df[df["symbol"] == sym].sort_values("date").reset_index(drop=True)
        m = meta[meta["symbol"] == sym].iloc[0]
        species = Species.from_row(m)
        acts = act_row(g)
        seed = sum(ord(c) for c in sym)
        y = header + r * (row_h + gap_y)
        for i, act in enumerate(ACTS):
            x = pad + i * (CELL[0] + gap_x)
            img.alpha_composite(panel(acts[act], species, seed + i * 7, caption_h=cap),
                                (x, y))

    d = ImageDraw.Draw(img)
    d.text((w / 2, h - 44),
           "floor price in ETH · petal count fixed by species · petals shed "
           "and colour drained in proportion to drawdown from peak",
           font=serif_font(13), fill=FAINT + (255,), anchor="mm")
    d.text((w / 2, h - 22),
           "GraveNFT Yard — hand-compiled monthly floors, Jan 2021 → Oct 2026",
           font=serif_font(12), fill=FAINT + (255,), anchor="mm")
    return img


# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    PLATES.mkdir(parents=True, exist_ok=True)
    meta = pd.read_csv(ROOT / "data" / "collections.csv")
    meta["symbol"] = meta["symbol"].str.lower()
    df = decorate(load_prices())

    for sym in meta["symbol"]:
        img = lifecycle_plate(sym, meta, df)
        path = PLATES / f"lifecycle_{sym}.png"
        img.save(path)
        print(f"wrote {path.relative_to(ROOT)}")

    for date in ("2021-11-01", "2022-04-01", "2026-10-01"):
        img = garden_plate(pd.Timestamp(date), meta, df)
        path = PLATES / f"garden_{date}.png"
        img.save(path)
        print(f"wrote {path.relative_to(ROOT)}")

    grid = lifecycle_grid(meta, df)
    grid.save(PLATES / "lifecycle_grid.png")
    print(f"wrote {(PLATES / 'lifecycle_grid.png').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
