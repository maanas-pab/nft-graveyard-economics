# 🪦 GraveNFT Yard

**An economic autopsy of five blue-chip NFTs — told in flowers that wilt with the floor price.**

[![CI](https://github.com/maanas-pab/nft-graveyard-economics/actions/workflows/ci.yml/badge.svg)](https://github.com/maanas-pab/nft-graveyard-economics/actions/workflows/ci.yml)
[![Live site](https://img.shields.io/badge/live-GitHub%20Pages-2a6b4a?logo=githubpages&logoColor=white)](https://maanas-pab.github.io/nft-graveyard-economics/)
[![Tests](https://img.shields.io/badge/tests-69%20passed-brightgreen)](https://github.com/maanas-pab/nft-graveyard-economics/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-d0a04a)](LICENSE)

<p align="center">
  <img src="assets/garden-anim.gif" alt="Five flowers blooming in April 2022, then wilting month by month until only headstones remain" width="900">
</p>

In **April 2022** the five most famous NFT collections on Earth held **$9.98 billion** of floor value — 3.22M ETH under five species of pixel botany. By **October 2026** they hold **$426 million**. **95.7% of it is gone.**

This project grows that number as a garden. Every collection is a flower. Every month is a frame. The floor price decides whether it blooms — or rots on the vine.

- 🌸 **Interactive** — scrub 70 months on the live site: play, pause, 0.5×/1×/2×, jump to any of 17 market events, share any month as a URL
- 🌾 **Generative art** — one price→botany engine, drawn twice: Pillow prints the specimen plates, canvas animates the live garden
- 📉 **Honest economics** — monthly floors in ETH *and* USD, drawdowns from running all-time highs, event-annotated, provenance documented
- ✅ **Tested** — 69 pytest checks pin the headline numbers and prove the wilt mapping is monotone, bounded, and deterministic

---

## 🖼️ The garden

Drag the timeline and watch the money leave. **April 2022 — the top of the bubble:**

<p align="center">
  <img src="assets/site/garden_peak.png" alt="The garden at April 2022: five flowers in full bloom, combined floor $9.98B" width="900">
</p>

**October 2026 — the aftermath.** Colour drained to leaf-litter brown, petals shed on the soil, stems collapsed, and a headstone per flower engraved with its drawdown. Only CryptoPunks stand at −90%; the rest are down 97–99%:

<p align="center">
  <img src="assets/site/garden_wilt.png" alt="The garden at October 2026: five wilted flowers with headstones showing −90% to −99% drawdowns" width="900">
</p>

> **Open the live site →** [maanas-pab.github.io/nft-graveyard-economics](https://maanas-pab.github.io/nft-graveyard-economics/)
> Deep links work: [`#2022-04`](https://maanas-pab.github.io/nft-graveyard-economics/#2022-04) opens the peak,
> [`#2026-10`](https://maanas-pab.github.io/nft-graveyard-economics/#2026-10) opens the aftermath,
> [`#play`](https://maanas-pab.github.io/nft-graveyard-economics/#play) plays all 70 months.

---

## 🌱 How price becomes botany

Every visual property of a flower is a pure function of two numbers: the current floor and the collection's running all-time high. Let **`r = floor / ATH`** (clipped to 0–1):

| Parameter | Formula | What you see |
|---|---|---|
| **Bloom size** | `0.085 + 0.115 · ln(1+floor) / ln(1+ATH)` | head radius. Log scale, because a 130 ETH floor is 43× the price of 3 ETH but must not be 43× the bloom |
| **Droop** | `(1 − r)^1.15` | the stem bows and the petals sag toward the soil |
| **Petal shed** | `((0.55 − r) / 0.55)^1.4` | petals detach and lie flattened on the ground — **zero above 55% of ATH**, then accelerating |
| **Saturation** | `0.18 + 0.82 · r^0.65` | colour drains toward leaf-litter brown |
| **Value** | `0.30 + 0.70 · r^0.55` | the bloom darkens as it dies |
| **Stem lean** | `droop × ±0.16` | mirror-image lean, alternating by seed so the row never looks stamped |
| **Headstone** | when drawdown ≤ −90% | engraved with the number: `−97%`, `−99%` |

Two curves do the emotional work. **Shed** is flat until the floor breaks — nothing falls while prices are merely "down a bit" — then petals drop off in a rush. **Saturation** uses `r^0.65`, so colour fades slowly at first and then all at once, which is what the crash actually felt like.

### Five species, one per collection

| Collection | Genus | Petals | Petal shape | Accent | Launched |
|---|---|---:|---|---|---|
| CryptoPunks | *Pixela* | 6 | blocky | `#7FE0C8` | 2017-06 (free claim) |
| Bored Ape Yacht Club | *Simia* | 8 | round | `#D9A441` | 2021-05 @ 0.08 ETH |
| Azuki | *Phaseolus* | 5 | pointed | `#E4553F` | 2022-01 @ 1.00 ETH |
| Doodles | *Pictura* | 7 | round | `#F2A0C4` | 2021-09 @ 0.12 ETH |
| Moonbirds | *Strix* | 6 | pointed | `#8FA8E8` | 2022-04 @ 1.50 ETH |

The whole graveyard at four moments each — **launch · peak · crash · today** — one row per species:

<p align="center">
  <img src="assets/plates/lifecycle_grid.png" alt="Lifecycle plate: all five collections rendered at launch, peak (Apr 2022), crash (Nov 2022) and today (Oct 2026)" width="620">
</p>

---
