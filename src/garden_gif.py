"""The garden, month by month: five flowers blooming and dying over 70 months.

Renders assets/garden-anim.gif — the README's opening frame.

Design notes:
  * flowers render once per (collection, month) and are cached — the renderer
    is deterministic, so there are only 70 x 5 unique cells.
  * the paper ground is flat, so the frame quantises cleanly to 256 colours.
  * captions are stamped with PIL after compositing, keeping type crisp.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

from .flower import Species, bloom_for, paper, render_flower, serif_font
from .pipeline import decorate, garden_totals, load_prices

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "garden-anim.gif"

CELL = (240, 340)
CAP = 64
PAD, GAP = 40, 16
HEADER, FOOTER = 132, 66
INK = (58, 48, 38)
FAINT = (140, 126, 108)
RULE = (188, 174, 150)
ALERT = (176, 65, 42)

FRAME_MS = 90        # ~11 fps: slow enough to read a number, fast enough to loop


def _usd(v: float) -> str:
    if v >= 1e9:
        return f"${v / 1e9:.2f}B"
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    return f"${v / 1e3:.0f}K"


def build_frames() -> list[Image.Image]:
    meta_path = ROOT / "data" / "collections.csv"
    import pandas as pd

    meta = pd.read_csv(meta_path)
    meta["symbol"] = meta["symbol"].str.lower()
    df = decorate(load_prices())
    tot = garden_totals(df).reset_index(drop=True)

    order = ["punks", "bayc", "azuki", "doodles", "moonbirds"]
    months = sorted(df["date"].unique())
    peak_usd = tot["peak_market_usd"].max()

    # cache: flower cell per (symbol, month-index)
    cache: dict[tuple[str, int], Image.Image] = {}
    for sym in order:
        g = df[df["symbol"] == sym].sort_values("date")
        m = meta[meta["symbol"] == sym].iloc[0]
        species = Species.from_row(m)
        seed = sum(ord(c) for c in sym)
        rows = {d: r for d, r in zip(g["date"], g.to_dict("records"))}
        for i, month in enumerate(months):
            if month not in rows:
                continue
            r = rows[month]
            b = bloom_for(float(r["floor_eth"]), float(r["ath_eth"]), CELL, seed)
            epitaph = (f"-{abs(r['drawdown_pct']):.0f}%"
                       if r["drawdown_pct"] <= -90 else None)
            cell = paper(CELL)
            cell.alpha_composite(render_flower(CELL, species, b, seed=seed,
                                               epitaph=epitaph))
            cache[(sym, i)] = cell

    w = PAD * 2 + CELL[0] * 5 + GAP * 4
    h = HEADER + CELL[1] + CAP + FOOTER
    frames: list[Image.Image] = []

    f_title = serif_font(40)
    f_sub = serif_font(17)
    f_month = serif_font(26)
    f_stat = serif_font(14)
    f_name = serif_font(13)

    for i, month in enumerate(months):
        row_t = tot.iloc[i]
        stamp = pd.Timestamp(month).strftime("%b %Y").upper()
        frame = paper((w, h), tone=(247, 242, 233, 255))
        d = ImageDraw.Draw(frame)
        d.rectangle([16, 16, w - 16, h - 16], outline=RULE + (255,), width=2)

        d.text((w / 2, 52), "GraveNFT Yard", font=f_title,
               fill=INK + (255,), anchor="mm")
        destroyed = row_t["destroyed_pct"]
        sub = (f"combined floor value {_usd(row_t['market_usd'])}"
               f"   ·   {destroyed:.0f}% below the April 2022 peak")
        d.text((w / 2, 94), sub, font=f_sub,
               fill=ALERT if destroyed > 50 else FAINT + (255,), anchor="mm")
        d.text((w / 2, 118), stamp, font=f_stat,
               fill=FAINT + (255,), anchor="mm")

        for j, sym in enumerate(order):
            x = PAD + j * (CELL[0] + GAP)
            cell = cache.get((sym, i))
            if cell is None:                     # pre-launch: an empty plot
                cell = paper(CELL)
                d2 = ImageDraw.Draw(cell)
                d2.text((CELL[0] / 2, CELL[1] / 2), "not yet planted",
                        font=f_name, fill=(196, 186, 168, 255), anchor="mm")
            frame.alpha_composite(cell, (x, HEADER))

            # per-collection caption under each plot
            g = df[(df["symbol"] == sym) & (df["date"] == month)]
            d = ImageDraw.Draw(frame)
            cy = HEADER + CELL[1] + 20
            if len(g):
                r = g.iloc[0]
                d.line([(x + CELL[0] * 0.14, cy - 8),
                        (x + CELL[0] * 0.86, cy - 8)], fill=RULE + (255,), width=1)
                d.text((x + CELL[0] / 2, cy + 6), sym.upper(), font=f_stat,
                       fill=FAINT + (255,), anchor="mm")
                col = ALERT if r["drawdown_pct"] <= -90 else INK
                d.text((x + CELL[0] / 2, cy + 30),
                       f"{r['floor_eth']:,.2f} ETH", font=f_name,
                       fill=col + (255,), anchor="mm")
            else:
                d.text((x + CELL[0] / 2, cy + 16), "—", font=f_stat,
                       fill=(196, 186, 168, 255), anchor="mm")

        # progress hairline
        d = ImageDraw.Draw(frame)
        px0, px1 = PAD, w - PAD
        d.line([(px0, h - 40), (px1, h - 40)], fill=RULE + (255,), width=2)
        prog = PAD + (px1 - px0) * (i / max(1, len(months) - 1))
        d.line([(px0, h - 40), (prog, h - 40)], fill=INK + (255,), width=2)
        d.ellipse([prog - 4, h - 44, prog + 4, h - 36], fill=INK + (255,))

        frames.append(frame.convert("P", palette=Image.ADAPTIVE, colors=256))

    return frames


def main(argv=None) -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames = build_frames()
    frames[0].save(
        OUT, save_all=True, append_images=frames[1:], duration=FRAME_MS,
        loop=0, optimize=True, disposal=2,
    )
    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(frames)} frames, {kb:,.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
