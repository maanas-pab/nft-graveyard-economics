"""Economics charts: the numbers behind the wilt. Renders to assets/charts/.

    prices.png        five floor prices, log scale, annotated with the events
    drawdown.png      % below running ATH — the shared gravity well
    destruction.png   combined floor value in USD, and the $9.5B that vanished
    petals.png        bloom parameter per collection, stacked as a heat strip

Style: warm paper ground, hairline rules, restrained ink — so the charts read
as plates from the same book as the flowers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from .pipeline import decorate, garden_totals, load_events, load_prices  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHARTS = ROOT / "assets" / "charts"

PAPER = "#f6f1e7"
INK = "#3a3026"
FAINT = "#8c7e6c"
RULE = "#bc9ea6" if False else "#bcaea6"
GRID = "#ddd3c1"

PALETTE = {
    "bayc": "#d9a441",
    "punks": "#7fe0c8",
    "azuki": "#e4553f",
    "doodles": "#f2a0c4",
    "moonbirds": "#8fa8e8",
}
LABELS = {
    "bayc": "Bored Ape Yacht Club",
    "punks": "CryptoPunks",
    "azuki": "Azuki",
    "doodles": "Doodles",
    "moonbirds": "Moonbirds",
}

plt.rcParams.update({
    "figure.facecolor": PAPER,
    "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": FAINT,
    "ytick.color": FAINT,
    "axes.edgecolor": GRID,
    "axes.linewidth": 0.8,
    "font.family": "serif",
    "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
    "font.size": 11,
    "axes.titlesize": 15,
    "axes.titleweight": "normal",
    "legend.frameon": False,
})


def _money(x, _pos=None) -> str:
    if x >= 1e9:
        return f"${x / 1e9:g}B"
    if x >= 1e6:
        return f"${x / 1e6:g}M"
    if x >= 1e3:
        return f"${x / 1e3:g}K"
    return f"${x:g}"


def _frame(ax, right=False):
    for side in ("top", "right"):
        ax.spines[side].set_visible(not right if side == "right" else False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)


def _events(ax, ev, y, kinds=("crash", "ath", "birth"), fs=8.5):
    for _, e in ev.iterrows():
        if e["kind"] not in kinds:
            continue
        ax.axvline(e["date"], color=RULE, linewidth=0.9,
                   linestyle=(0, (4, 3)), alpha=0.85, zorder=1)


def _date_axis(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=(4, 7, 10)))


# --------------------------------------------------------------------------- #
# 1. floor prices, log scale                                                   #
# --------------------------------------------------------------------------- #

def chart_prices(df, ev) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    _events(ax, ev, 0)
    _frame(ax)
    _date_axis(ax)

    # offsets staggered so the April 2022 cluster doesn't pile up;
    # (dx, dy, ha) — punks goes left, bayc right, both clear of the frame
    offsets = {"punks": (-46, 4, "right"), "bayc": (46, 2, "left"),
               "moonbirds": (30, 8, "left"), "azuki": (-34, -4, "right"),
               "doodles": (8, -18, "center")}

    for sym, g in df.groupby("symbol"):
        ax.plot(g["date"], g["floor_eth"], color=PALETTE[sym], linewidth=2.1,
                label=LABELS[sym], zorder=3, solid_capstyle="round")
        peak = g.loc[g["floor_eth"].idxmax()]
        ax.scatter([peak["date"]], [peak["floor_eth"]], s=34, color=PALETTE[sym],
                   edgecolor=PAPER, linewidth=1.3, zorder=4)
        dx, dy, ha = offsets.get(sym, (0, 9, "center"))
        ax.annotate(f"{peak['floor_eth']:,.0f} ETH",
                    (peak["date"], peak["floor_eth"]),
                    textcoords="offset points", xytext=(dx, dy),
                    ha=ha, fontsize=9, color=INK, zorder=5)

    ax.set_yscale("log")
    ax.set_ylim(0.08, 320)
    ax.set_yticks([0.1, 0.3, 1, 3, 10, 30, 100, 300])
    ax.get_yaxis().set_major_formatter(FuncFormatter(
        lambda v, _p: f"{v:g}" if v >= 1 else f"{v:g}"))
    ax.set_ylabel("floor price (ETH, log scale)")
    ax.set_title("Five blue-chip floors, 2021 to 2026 — log scale",
                 loc="left", pad=16)
    ax.text(0, 1.02, "each peak marked; dashed lines = turning points",
            transform=ax.transAxes, fontsize=9.5, color=FAINT)

    ax.legend(loc="lower left", fontsize=9.5, ncol=2, labelcolor=INK)
    ax.set_xlim(pd.Timestamp("2020-12-01"), pd.Timestamp("2026-11-15"))
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
# 2. drawdown from running ATH                                                 #
# --------------------------------------------------------------------------- #

def chart_drawdown(df, ev) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    _frame(ax)
    _date_axis(ax)
    _events(ax, ev, 0, kinds=("crash",))

    for sym, g in df.groupby("symbol"):
        ax.plot(g["date"], g["drawdown_pct"], color=PALETTE[sym], linewidth=1.9,
                label=LABELS[sym], zorder=3, solid_capstyle="round")

    ax.set_ylim(-102, 4)
    ax.set_yticks([0, -25, -50, -75, -100])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:.0f}%"))
    ax.set_ylabel("below running all-time high")
    ax.axhline(-90, color="#b0412a", linewidth=0.9, linestyle=(0, (5, 4)))
    ax.annotate("everything crosses −90% eventually",
                (pd.Timestamp("2025-08-01"), -90),
                textcoords="offset points", xytext=(0, 8),
                ha="center", fontsize=9.5, color="#b0412a")

    ax.set_title("Drawdown from peak — one long fall", loc="left", pad=16)
    ax.text(0, 1.02, "monthly close vs. the highest floor seen to that date",
            transform=ax.transAxes, fontsize=9.5, color=FAINT)
    ax.legend(loc="upper right", fontsize=9.5, ncol=2, labelcolor=INK,
              bbox_to_anchor=(0.99, 0.99))
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
# 3. value destruction                                                         #
# --------------------------------------------------------------------------- #

def chart_destruction(tot) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(11.5, 6.0))
    _frame(ax)
    _date_axis(ax)

    peak = tot.loc[tot["market_usd"].idxmax()]
    ax.fill_between(tot["date"], tot["market_usd"], color="#c9553f", alpha=0.16,
                    zorder=2)
    ax.plot(tot["date"], tot["market_usd"], color="#b0412a", linewidth=2.3,
            zorder=3, label="combined floor value")

    # the phantom peak line: what it would take to be whole again
    ax.plot(tot["date"], tot["peak_market_usd"], color=FAINT, linewidth=1.2,
            linestyle=(0, (5, 4)), zorder=2, label="previous peak (unreached)")

    last = tot.iloc[-1]
    ax.annotate(f"${peak['market_usd'] / 1e9:,.2f}B\nApr 2022",
                (peak["date"], peak["market_usd"]),
                textcoords="offset points", xytext=(14, -46),
                fontsize=10.5, color=INK, ha="left")
    ax.annotate(f"${last['market_usd'] / 1e6:,.0f}M\nOct 2026",
                (last["date"], last["market_usd"]),
                textcoords="offset points", xytext=(-14, 46),
                fontsize=10.5, color="#b0412a", ha="right")

    ax.yaxis.set_major_formatter(FuncFormatter(_money))
    ax.set_ylabel("sum of floor × supply, all five collections")
    ax.set_title("What the five were worth, and what is left",
                 loc="left", pad=16)
    ax.text(0, 1.02,
            f"peak ${peak['market_usd'] / 1e9:.2f}B  falls to  "
            f"${last['market_usd'] / 1e6:.0f}M   ·   "
            f"−${last['destroyed_usd'] / 1e9:.2f}B destroyed "
            f"({last['destroyed_pct']:.1f}% of peak)",
            transform=ax.transAxes, fontsize=10, color=FAINT)
    ax.legend(loc="center right", fontsize=9.5, labelcolor=INK,
              bbox_to_anchor=(0.99, 0.52))
    ax.set_xlim(pd.Timestamp("2021-04-01"), pd.Timestamp("2026-11-15"))
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
# 4. the bloom parameter as a heat strip                                        #
# --------------------------------------------------------------------------- #

def chart_bloom(df) -> plt.Figure:
    syms = ["punks", "bayc", "azuki", "doodles", "moonbirds"]
    months = sorted(df["date"].unique())
    grid = np.full((len(syms), len(months)), np.nan)

    idx = {m: i for i, m in enumerate(months)}
    for r, sym in enumerate(syms):
        g = df[df["symbol"] == sym]
        for _, row in g.iterrows():
            grid[r, idx[row["date"]]] = row["ratio"]

    fig, ax = plt.subplots(figsize=(11.5, 3.3))
    cmap = plt.cm.YlOrBr.copy()
    cmap.set_bad("#efe8db")
    im = ax.imshow(grid, aspect="auto", cmap=cmap, vmin=0, vmax=1,
                   interpolation="nearest",
                   extent=[mdates.date2num(months[0]),
                           mdates.date2num(months[-1]), len(syms) - 0.5, -0.5])

    ax.set_yticks(range(len(syms)))
    ax.set_yticklabels([LABELS[s] for s in syms], fontsize=10, color=INK)
    _date_axis(ax)
    ax.grid(False)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    cb = fig.colorbar(im, ax=ax, pad=0.012, fraction=0.022)
    cb.set_label("floor as percent of that collection's own ATH", fontsize=9.5,
                 color=INK)
    cb.ax.tick_params(colors=FAINT, labelsize=8.5)
    cb.outline.set_edgecolor(GRID)

    ax.set_title("The bloom parameter — colour of every flower in this repo",
                 loc="left", pad=14)
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    CHARTS.mkdir(parents=True, exist_ok=True)
    df = decorate(load_prices())
    ev = load_events()
    tot = garden_totals(df)

    for name, fig in [
        ("prices", chart_prices(df, ev)),
        ("drawdown", chart_drawdown(df, ev)),
        ("destruction", chart_destruction(tot)),
        ("bloom", chart_bloom(df)),
    ]:
        path = CHARTS / f"{name}.png"
        fig.savefig(path, dpi=170, bbox_inches="tight")
        plt.close(fig)
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
