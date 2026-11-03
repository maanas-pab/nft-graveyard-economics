"""Data-integrity tests: the hand-compiled CSVs must stay honest.

These guard the things that would silently corrupt every downstream image:

  * the monthly grid is continuous (no missing months, no duplicates)
  * prices are positive where they exist, blank (not zero) before launch
  * each collection's series starts at its launch month and never stops
  * ETH/USD covers every month the prices cover
  * events fall inside the observed window and use known kinds
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

MONTH_FMT = "%Y-%m"
KNOWN_KINDS = {"birth", "mania", "ath", "peak", "crash", "bleed", "bounce", "end"}
SYMBOLS = ["bayc", "punks", "azuki", "doodles", "moonbirds"]


@pytest.fixture(scope="module")
def collections() -> pd.DataFrame:
    return pd.read_csv(DATA / "collections.csv")


@pytest.fixture(scope="module")
def prices() -> pd.DataFrame:
    return pd.read_csv(DATA / "floor_prices.csv")


@pytest.fixture(scope="module")
def eth() -> pd.DataFrame:
    return pd.read_csv(DATA / "eth_usd.csv")


@pytest.fixture(scope="module")
def events() -> pd.DataFrame:
    return pd.read_csv(DATA / "events.csv")


# --------------------------------------------------------------------------- #
# collections                                                                  #
# --------------------------------------------------------------------------- #

def test_five_collections_with_unique_symbols(collections):
    assert len(collections) == 5
    assert sorted(collections["symbol"]) == sorted(SYMBOLS)
    assert collections["symbol"].is_unique


def test_botanical_identity_is_complete(collections):
    """Every species needs petals, a shape, an accent, and a genus."""
    assert collections["petals"].between(4, 12).all()
    assert set(collections["petal_shape"]) <= {"round", "pointed", "blocky"}
    assert collections["accent_hex"].str.fullmatch(r"#[0-9A-Fa-f]{6}").all()
    assert collections["genus"].is_unique
    assert collections["collection"].is_unique


def test_supply_and_launch_are_sane(collections):
    assert (collections["supply"] > 0).all()
    # >= 0, not > 0: CryptoPunks were claimed free (gas only)
    assert (collections["mint_price_eth"] >= 0).all()
    launches = pd.to_datetime(collections["launch_date"])
    assert launches.between("2017-01-01", "2026-10-01").all()


# --------------------------------------------------------------------------- #
# floor prices                                                                 #
# --------------------------------------------------------------------------- #

def test_monthly_grid_is_continuous(prices):
    """70 rows, Jan 2021 -> Oct 2026, one per month, no gaps or dupes."""
    dates = pd.to_datetime(prices["date"], format=MONTH_FMT)
    expected = pd.date_range("2021-01-01", "2026-10-01", freq="MS")
    assert list(dates) == list(expected)
    assert dates.is_unique


def test_columns_match_collections(prices, collections):
    assert sorted(c for c in prices.columns if c != "date") == sorted(
        collections["symbol"]
    )


def test_prices_are_positive_or_blank(prices):
    """Pre-launch months are NaN (not 0); live months are strictly positive."""
    for sym in SYMBOLS:
        series = prices[sym]
        assert not (series == 0).any(), f"{sym} contains a zero floor"
        assert (series.dropna() > 0).all(), f"{sym} has a non-positive floor"
        # blanks, if any, must all come before the first printed price
        first_live = series.first_valid_index()
        if first_live > 0:
            assert series.iloc[:first_live].isna().all()


def test_series_start_at_launch_and_run_to_the_end(prices, collections):
    """A series starts in the calendar month of its mint and never stops.

    Launches are mid-month (Azuki minted Jan 12), so the first printed
    floor is the first of that month.
    """
    for _, row in collections.iterrows():
        series = prices[row["symbol"]]
        first = series.first_valid_index()
        launch_month = pd.Timestamp(row["launch_date"]).to_period("M").to_timestamp()
        expected_start = max(launch_month, pd.Timestamp("2021-01-01"))
        assert pd.Timestamp(prices.loc[first, "date"]) == expected_start, (
            f"{row['symbol']} series should start at {expected_start.date()}"
        )
        assert pd.Timestamp(prices.loc[series.last_valid_index(), "date"]) == \
            pd.Timestamp("2026-10-01"), f"{row['symbol']} series stops early"


def test_no_collection_collapses_to_zero(prices):
    """Floors fall hard, but a live bid never prints 0.0 in this dataset."""
    for sym in SYMBOLS:
        assert prices[sym].dropna().min() > 0


# --------------------------------------------------------------------------- #
# ETH/USD                                                                      #
# --------------------------------------------------------------------------- #

def test_eth_usd_covers_every_month(eth, prices):
    eth_dates = set(pd.to_datetime(eth["date"], format=MONTH_FMT))
    price_dates = set(pd.to_datetime(prices["date"], format=MONTH_FMT))
    assert price_dates <= eth_dates, "missing ETH/USD for some month"
    assert eth["eth_usd"].between(100, 20000).all()


# --------------------------------------------------------------------------- #
# events                                                                       #
# --------------------------------------------------------------------------- #

def test_events_use_known_kinds(events):
    assert set(events["kind"]) <= KNOWN_KINDS


def test_events_fall_inside_the_observed_window(events):
    dates = pd.to_datetime(events["date"])
    assert dates.between("2021-01-01", "2026-10-01").all()
    assert dates.is_unique
    assert (dates.diff().dropna() > pd.Timedelta(0)).all(), "events not sorted"


def test_events_have_labels(events):
    assert events["label"].str.len().gt(10).all()
    assert not events["label"].duplicated().any()
