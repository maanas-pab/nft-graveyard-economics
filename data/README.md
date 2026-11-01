# Data

Hand-compiled datasets. Nothing here is fetched from an API — this is a
curated snapshot project, and it says so.

## Files

| File | Rows | What it is |
|---|---|---|
| `floor_prices.csv` | 70 months × 5 collections | **The dataset.** Monthly floor price in ETH for five famous NFT collections, Jan 2021 → Oct 2026. Blank cells before a collection launched (BAYC mints May 2021, Azuki Jan 2022, Moonbirds Apr 2022, Doodles Sep 2021). |
| `eth_usd.csv` | 70 | Month-end ETH/USD reference rate, so floors can be re-expressed in dollars. |
| `collections.csv` | 5 | Static metadata per collection: supply, launch date, mint price, petal count/shape for the botanical renderer, accent hex. |
| `events.csv` | 17 | Turning points used to annotate charts: births, ATHs, crashes, bounces, the long bleed. |

## Series and coverage

- **Frequency:** monthly (month-end observation).
- **Range:** 2021-01 → 2026-10 (70 observations).
- **Units:** floor price in **ETH** (native), USD derived as `floor_eth × eth_usd`.
- **Pre-launch cells** are left empty rather than zero — zero would imply a
  floor of 0 ETH, which is a price, not an absence.

## Provenance & caveats

Floor prices are **manually compiled approximations** of observed marketplace
floors (OpenSea/Blur era) rounded for readability. They are good enough to
trace the shape of the bubble and its collapse; they are **not** settlement
data and must not be used for anything resembling a financial decision.

Known simplifications:

1. Monthly sampling hides intra-month extremes (real floors were more violent
   than these curves — drawdowns are *understated* at the monthly grain).
2. Loots/traits and collection-wide offers are ignored; a single illiterate
   sweep can move a floor without anyone "selling".
3. The five collections are a **survivor-biased** sample of famous projects;
   thousands of collections went to exactly zero and are not represented —
   which makes the demonstrated losses a *lower* bound on the true carnage.
4. `eth_usd` is a coarse month-end reference rate, not a VWAP.

## Schema notes

```
floor_prices.csv   date,collection,floor_eth,floor_usd   (long form after build)
eth_usd.csv        date,eth_usd
collections.csv    symbol,collection,supply,launch_date,mint_price_eth,
                   petals,petal_shape,accent_hex,genus
events.csv         date,label,kind
```

`kind ∈ {birth, mania, ath, peak, crash, bounce, bleed, end}` drives annotation
styling in the charts.
