"""Tests for the pandas pipeline: derived metrics and the web payload.

The headline numbers ($9.98B peak, 95.7% destroyed) are quoted in the
README and the site — these tests pin them so the story can't drift
silently when the data changes.
"""

from __future__ import annotations

import json

import pytest

from src.pipeline import (decorate, garden_totals, load_events,
                          load_prices, summary, web_payload)


@pytest.fixture(scope="module")
def df():
    return decorate(load_prices())


@pytest.fixture(scope="module")
def totals(df):
    return garden_totals(df)


# --------------------------------------------------------------------------- #
# decorate                                                                     #
# --------------------------------------------------------------------------- #

def test_running_ath_is_monotone_per_collection(df):
    for sym, g in df.groupby("symbol"):
        ath = g.sort_values("date")["ath_eth"]
        assert (ath.diff().dropna() >= 0).all(), f"{sym} ATH went backwards"


def test_ratio_and_drawdown_are_bounded(df):
    assert df["ratio"].between(0.0, 1.0).all()
    assert df["drawdown_pct"].between(-100.0, 0.0).all()
    # drawdown is exactly ratio - 1, in percent
    assert (df["drawdown_pct"] == (df["ratio"] - 1.0) * 100.0).all()


def test_botanical_params_follow_the_ratio(df):
    """All three botanical params are pure functions of the ratio.

    Sorted by ratio: colour rises with it; droop and shed fall away as the
    floor recovers (they are computed from the current price, not history).
    """
    ordered = df.dropna(subset=["ratio"]).sort_values("ratio")
    droop = ordered["droop"].to_numpy()
    sat = ordered["saturation"].to_numpy()
    shed = ordered["shed"].to_numpy()
    assert (sat[1:] >= sat[:-1] - 1e-12).all()      # colour revives upward
    assert (droop[1:] <= droop[:-1] + 1e-12).all()  # droop relaxes upward
    assert (shed[1:] <= shed[:-1] + 1e-12).all()    # shed thins upward


def test_market_value_equals_floor_times_supply(df):
    assert (df["market_eth"] == df["floor_eth"] * df["supply"]).all()
    assert (df["market_usd"] == df["floor_usd"] * df["supply"]).all()


def test_floor_usd_tracks_eth_usd(df):
    """floor_usd must equal floor_eth times that month's ETH price.

    Cross-checked against the source CSV, not the pipeline's own column.
    """
    from pathlib import Path

    import pandas as pd

    eth = pd.read_csv(Path(__file__).resolve().parent.parent /
                      "data" / "eth_usd.csv")
    eth["date"] = pd.to_datetime(eth["date"], format="%Y-%m")
    eth = eth.rename(columns={"eth_usd": "eth_source"})
    merged = df.merge(eth, on="date", how="left")
    implied = merged["floor_usd"] / merged["floor_eth"]
    # the CSV rounds ETH/USD to whole dollars, so allow a little slack
    assert (implied - merged["eth_source"]).abs().div(
        merged["eth_source"]).lt(0.01).all()


# --------------------------------------------------------------------------- #
# garden totals — the headline economics                                       #
# --------------------------------------------------------------------------- #

def test_peak_is_april_2022_at_9_98b(totals):
    peak = totals.loc[totals["market_usd"].idxmax()]
    assert peak["date"].strftime("%Y-%m") == "2022-04"
    assert peak["market_usd"] == pytest.approx(9_982_000_000, rel=1e-6)
    assert peak["market_eth"] == pytest.approx(3_220_000, rel=1e-6)


def test_destruction_is_95_7_percent(totals):
    peak = totals["market_usd"].max()
    last = totals.iloc[-1]["market_usd"]
    destroyed = peak - last
    assert last == pytest.approx(426_375_000, rel=1e-6)
    assert destroyed == pytest.approx(9_555_625_000, rel=1e-6)
    assert destroyed / peak * 100 == pytest.approx(95.7, abs=0.05)
    # the payload's own destroyed column must agree with the arithmetic
    assert totals.iloc[-1]["destroyed_usd"] == pytest.approx(destroyed, rel=1e-9)


def test_destroyed_is_never_negative(totals):
    assert (totals["destroyed_usd"] >= 0).all()


def test_totals_index_is_the_full_monthly_grid(totals):
    dates = list(totals["date"])
    assert len(dates) == 70
    assert dates[0].strftime("%Y-%m") == "2021-01"
    assert dates[-1].strftime("%Y-%m") == "2026-10"


# --------------------------------------------------------------------------- #
# summary — one row per collection                                             #
# --------------------------------------------------------------------------- #

def test_summary_covers_all_five_sorted_by_pain(df):
    s = summary(df)
    assert len(s) == 5
    # worst first: -99.2, -98.7, ... -90.0 (i.e. ascending numeric order)
    assert list(s["symbol"]) == ["moonbirds", "doodles", "bayc", "azuki",
                                 "punks"]
    assert s["drawdown_pct"].is_monotonic_increasing


def test_summary_drawdowns_match_the_known_ashes(df):
    s = summary(df).set_index("symbol")
    expected = {"moonbirds": -99.2, "doodles": -98.7, "bayc": -97.6,
                "azuki": -97.5, "punks": -90.0}
    for sym, pct in expected.items():
        assert s.loc[sym, "drawdown_pct"] == pytest.approx(pct, abs=0.05)


# --------------------------------------------------------------------------- #
# web payload                                                                  #
# --------------------------------------------------------------------------- #

def test_web_payload_shape(df, totals):
    ev = load_events()
    p = web_payload(df, totals, ev)
    assert len(p["months"]) == 70
    assert len(p["eth_usd"]) == 70
    assert len(p["totals"]["market_usd"]) == 70
    assert sorted(p["series"]) == ["azuki", "bayc", "doodles", "moonbirds",
                                   "punks"]
    for series in p["series"].values():
        for key in ("floor_eth", "floor_usd", "ratio", "drawdown"):
            assert len(series[key]) == 70


def test_web_payload_is_json_serializable(df, totals):
    ev = load_events()
    p = web_payload(df, totals, ev)
    body = json.dumps(p, separators=(",", ":"))
    assert body.startswith("{") and json.loads(body)["generated"]


def test_web_payload_marks_pre_launch_as_null(df, totals):
    """The site draws 'not yet planted' from nulls — never from zeros."""
    p = web_payload(df, totals, load_events())
    azuki = p["series"]["azuki"]["floor_eth"]
    assert azuki[:12] == [None] * 12          # Jan 2021 .. Dec 2021
    assert azuki[12] is not None              # launches Jan 2022
    assert 0 not in azuki                     # a real floor is never 0


def test_web_payload_events_are_month_stamped(df, totals):
    p = web_payload(df, totals, load_events())
    assert len(p["events"]) == 17
    for e in p["events"]:
        assert len(e["date"]) == 7 and e["date"][4] == "-"
        assert e["date"] in p["months"]
