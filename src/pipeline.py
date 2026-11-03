"""pandas pipeline: manual CSVs -> one tidy metrics frame + a JSON payload.

Run:
    python3 -m src.pipeline            # -> build/metrics.csv  (+ summary)
    python3 -m src.pipeline --web      # -> site/data/garden.js (JSONP for the site)

Derivations, in order:

    floor_usd   = floor_eth * eth_usd
    ath_eth     = running max of floor_eth within the collection (per month)
    ratio       = floor_eth / ath_eth                    -> the bloom parameter
    drawdown    = (ratio - 1) * 100                      -> the headline number
    market_eth  = floor_eth * supply                     -> naive "market cap"
    lost_eth    = (ath_eth - floor_eth) * supply         -> wealth destroyed
    petal_count, shed, droop, saturation                 -> botanical params
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BUILD = ROOT / "build"
SITE_DATA = ROOT / "site" / "data"

MONTH_FMT = "%Y-%m"


# --------------------------------------------------------------------------- #
# loading                                                                      #
# --------------------------------------------------------------------------- #

def load_collections() -> pd.DataFrame:
    df = pd.read_csv(DATA / "collections.csv")
    df["symbol"] = df["symbol"].str.lower()
    return df


def load_prices() -> pd.DataFrame:
    """Wide CSV -> long tidy frame with USD conversion and static metadata."""
    wide = pd.read_csv(DATA / "floor_prices.csv")
    wide["date"] = pd.to_datetime(wide["date"], format=MONTH_FMT)
    long = wide.melt(id_vars="date", var_name="symbol", value_name="floor_eth")
    long = long.dropna(subset=["floor_eth"])          # pre-launch rows, not zeros
    long["symbol"] = long["symbol"].str.lower()

    eth = pd.read_csv(DATA / "eth_usd.csv")
    eth["date"] = pd.to_datetime(eth["date"], format=MONTH_FMT)
    long = long.merge(eth, on="date", how="left")
    long["floor_usd"] = long["floor_eth"] * long["eth_usd"]

    meta = load_collections()
    long = long.merge(
        meta[["symbol", "collection", "genus", "supply", "petals", "accent_hex"]],
        on="symbol", how="left",
    )
    return long.sort_values(["symbol", "date"]).reset_index(drop=True)


def load_events() -> pd.DataFrame:
    ev = pd.read_csv(DATA / "events.csv")
    ev["date"] = pd.to_datetime(ev["date"], format="%Y-%m-%d")
    return ev.sort_values("date").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# derivation                                                                   #
# --------------------------------------------------------------------------- #

def decorate(df: pd.DataFrame) -> pd.DataFrame:
    """Running ATH, drawdown, supply-level wealth numbers, botanical params."""
    df = df.copy()
    df["ath_eth"] = df.groupby("symbol")["floor_eth"].cummax()
    df["ratio"] = (df["floor_eth"] / df["ath_eth"]).clip(0.0, 1.0)
    df["drawdown_pct"] = (df["ratio"] - 1.0) * 100.0
    df["market_eth"] = df["floor_eth"] * df["supply"]
    df["market_usd"] = df["floor_usd"] * df["supply"]
    df["lost_eth"] = (df["ath_eth"] - df["floor_eth"]) * df["supply"]

    # botany: the same ratio the flower engine consumes, plus its components
    log_span = np_log(df["ath_eth"])
    df["bloom_size"] = 0.085 + 0.115 * (np_log(df["floor_eth"]) / log_span)
    df["droop"] = (1.0 - df["ratio"]) ** 1.15
    shed = ((0.55 - df["ratio"]) / 0.55).clip(0.0, 1.0)
    df["shed"] = shed ** 1.4
    df["saturation"] = 0.18 + 0.82 * df["ratio"] ** 0.65
    return df


def np_log(s: pd.Series) -> pd.Series:
    return s.clip(lower=0.0).map(lambda v: math.log1p(v))


def summary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per collection: the whole arc, in numbers."""
    rows = []
    for sym, g in df.groupby("symbol"):
        peak = g.loc[g["ath_eth"].idxmax()]
        ath_row = g.loc[g["floor_eth"].idxmax()]
        last = g.iloc[-1]
        rows.append({
            "symbol": sym,
            "collection": g["collection"].iloc[0],
            "launch": g["date"].min().date().isoformat(),
            "ath_eth": round(float(ath_row["floor_eth"]), 2),
            "ath_date": ath_row["date"].date().isoformat(),
            "ath_usd": f"{ath_row['floor_usd']:,.0f}",
            "peak_market_usd": f"{ath_row['floor_usd'] * ath_row['supply']:,.0f}",
            "last_eth": round(float(last["floor_eth"]), 2),
            "last_usd": f"{last['floor_usd']:,.0f}",
            "drawdown_pct": round(float(last["drawdown_pct"]), 1),
            "shed": int(round(float(last["shed"]) * 2 * last["petals"])),
            "petals": int(last["petals"]),
        })
    out = pd.DataFrame(rows).sort_values("drawdown_pct")
    return out.reset_index(drop=True)


def garden_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Combined thesis line: five collections as one portfolio, month by month."""
    g = (df.groupby("date")
           .agg(market_eth=("market_eth", "sum"),
                market_usd=("market_usd", "sum"),
                lost_eth=("lost_eth", "sum"),
                mean_ratio=("ratio", "mean"))
           .reset_index()
           .sort_values("date"))
    g["peak_market_usd"] = g["market_usd"].cummax()
    g["destroyed_usd"] = g["peak_market_usd"] - g["market_usd"]
    g["destroyed_pct"] = (1 - g["market_usd"] / g["peak_market_usd"]) * 100
    return g


# --------------------------------------------------------------------------- #
# web payload                                                                  #
# --------------------------------------------------------------------------- #

def web_payload(df: pd.DataFrame, tot: pd.DataFrame, ev: pd.DataFrame) -> dict:
    meta = load_collections()
    months = sorted(df["date"].unique())

    eth = pd.read_csv(DATA / "eth_usd.csv")
    eth["date"] = pd.to_datetime(eth["date"], format=MONTH_FMT)
    eth_idx = eth.set_index("date")["eth_usd"]

    series = {}
    for sym, g in df.groupby("symbol"):
        by_date = g.set_index("date")
        series[sym] = {
            "floor_eth": [round(float(by_date.at[m, "floor_eth"]), 4)
                          if m in by_date.index else None for m in months],
            "floor_usd": [round(float(by_date.at[m, "floor_usd"]), 0)
                          if m in by_date.index else None for m in months],
            "ratio": [round(float(by_date.at[m, "ratio"]), 4)
                      if m in by_date.index else None for m in months],
            "drawdown": [round(float(by_date.at[m, "drawdown_pct"]), 2)
                         if m in by_date.index else None for m in months],
        }

    t = tot.set_index("date")
    return {
        "months": [pd.Timestamp(m).strftime("%Y-%m") for m in months],
        "eth_usd": [round(float(eth_idx.loc[m]), 0) for m in months],
        "collections": meta.to_dict("records"),
        "series": series,
        "totals": {
            "market_eth": [round(float(t.at[m, "market_eth"]), 1) for m in months],
            "market_usd": [round(float(t.at[m, "market_usd"]), 0) for m in months],
            "destroyed_usd": [round(float(t.at[m, "destroyed_usd"]), 0) for m in months],
            "mean_ratio": [round(float(t.at[m, "mean_ratio"]), 4) for m in months],
        },
        "events": [
            {"date": pd.Timestamp(e["date"]).strftime("%Y-%m"),
             "label": e["label"], "kind": e["kind"]}
            for _, e in ev.iterrows()
        ],
        # data cutoff, not wall-clock: a rebuild must be byte-identical
        "generated": pd.Timestamp(months[-1]).strftime("%Y-%m"),
    }


def write_web(df: pd.DataFrame, tot: pd.DataFrame, ev: pd.DataFrame) -> Path:
    payload = web_payload(df, tot, ev)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    path = SITE_DATA / "garden.js"
    body = json.dumps(payload, separators=(",", ":"))
    path.write_text(f"window.GARDEN = {body};\n")
    return path


# --------------------------------------------------------------------------- #
# entrypoint                                                                   #
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--web", action="store_true",
                    help="also export site/data/garden.js")
    args = ap.parse_args(argv)

    df = decorate(load_prices())
    ev = load_events()
    tot = garden_totals(df)

    BUILD.mkdir(exist_ok=True)
    out = BUILD / "metrics.csv"
    df.to_csv(out, index=False)

    summ = summary(df)
    summ.to_csv(BUILD / "summary.csv", index=False)

    print(f"wrote {out.relative_to(ROOT)}  ({len(df)} rows)")
    print()
    print(summ.to_string(index=False))
    print()
    peak = tot.loc[tot["market_usd"].idxmax()]
    last = tot.iloc[-1]
    print(f"garden peak      : {peak['date'].date()}  "
          f"${peak['market_usd']:,.0f}  ({peak['market_eth']:,.0f} ETH)")
    print(f"today            : ${last['market_usd']:,.0f}  "
          f"({last['market_eth']:,.1f} ETH)")
    print(f"value destroyed  : ${last['destroyed_usd']:,.0f}  "
          f"({last['destroyed_pct']:.1f}% of peak)")

    if args.web:
        p = write_web(df, tot, ev)
        print(f"wrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
