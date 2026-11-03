"""Tests for the flower engine: the price-to-botany mapping must be
monotone, bounded, and deterministic.

If any of these fail, the pictures are lying about the data.
"""

from __future__ import annotations

import math

import pytest

from src.flower import Species, bloom_for, render_flower
from src.pipeline import load_collections

CELL = (300, 420)


@pytest.fixture(scope="module")
def species_rows():
    return load_collections()


def species_for(sym: str, rows) -> Species:
    row = rows[rows["symbol"] == sym].iloc[0]
    return Species.from_row(row)


# --------------------------------------------------------------------------- #
# bloom_for: the mapping itself                                                #
# --------------------------------------------------------------------------- #

def test_at_ath_the_flower_is_perfect():
    b = bloom_for(price=100.0, ath=100.0, cell=CELL, seed=0)
    assert b.ratio == pytest.approx(1.0)
    assert b.droop == 0.0
    assert b.shed == 0.0
    assert b.saturation == pytest.approx(1.0, abs=1e-6)
    assert b.value == pytest.approx(1.0, abs=1e-6)


def test_at_zero_price_the_flower_is_dead():
    b = bloom_for(price=0.0, ath=100.0, cell=CELL, seed=0)
    assert b.ratio == 0.0
    assert b.droop == pytest.approx(1.0)
    assert b.shed == pytest.approx(1.0)
    assert b.saturation == pytest.approx(0.18, abs=1e-9)
    assert b.value == pytest.approx(0.30, abs=1e-9)


def test_ratio_is_clipped_to_the_unit_interval():
    assert bloom_for(200.0, 100.0, CELL, 0).ratio == 1.0      # above ATH
    assert bloom_for(-5.0, 100.0, CELL, 0).ratio == 0.0       # nonsense input
    assert bloom_for(5.0, 0.0, CELL, 0).ratio == 0.0          # no ATH yet


@pytest.mark.parametrize("price,ath", [(100, 100), (60, 100), (10, 100),
                                       (3, 100), (0.5, 100)])
def test_droop_increases_as_price_falls(price, ath):
    """Lower floor -> heavier droop: the stem always collapses downward."""
    b = bloom_for(price, ath, CELL, 0)
    assert 0.0 <= b.droop <= 1.0
    if price < ath:
        assert b.droop > bloom_for(ath, ath, CELL, 0).droop


def test_petals_shed_only_after_the_floor_breaks():
    """Above 55% of ATH nothing falls; below it, shedding accelerates."""
    assert bloom_for(80.0, 100.0, CELL, 0).shed == 0.0
    assert bloom_for(55.0, 100.0, CELL, 0).shed == 0.0
    falling = bloom_for(20.0, 100.0, CELL, 0).shed
    buried = bloom_for(2.0, 100.0, CELL, 0).shed
    assert 0.0 < falling < buried <= 1.0


def test_colour_drains_monotonically():
    """Saturation and value fall as the ratio falls — no colour revivals."""
    prev_sat = prev_val = 2.0
    for price in [100, 70, 50, 30, 15, 5, 1]:
        b = bloom_for(price, 100.0, CELL, 0)
        assert b.saturation <= prev_sat
        assert b.value <= prev_val
        prev_sat, prev_val = b.saturation, b.value


def test_size_is_log_scaled_and_grows_with_price():
    """Log scale: 100 ETH is not 10x the bloom of 10 ETH."""
    small = bloom_for(10.0, 100.0, CELL, 0)
    big = bloom_for(100.0, 100.0, CELL, 0)
    assert 0 < small.size < big.size < 0.21
    # the head radius is a fraction of cell width, always inside the plot
    for price in (0, 1, 10, 100):
        b = bloom_for(price, 100.0, CELL, 0)
        assert 0.08 <= b.size <= 0.21


def test_size_is_not_linear_in_price():
    """A 10x price jump must not be a 10x bloom (that's the log scale)."""
    r10 = bloom_for(10.0, 1000.0, CELL, 0).size
    r100 = bloom_for(100.0, 1000.0, CELL, 0).size
    r1000 = bloom_for(1000.0, 1000.0, CELL, 0).size
    # each decade adds a similar slice of radius, not a multiple
    step1 = r100 - r10
    step2 = r1000 - r100
    assert step1 == pytest.approx(step2, rel=0.35)


def test_stem_lean_alternates_by_seed_but_tracks_droop():
    odd = bloom_for(10.0, 100.0, CELL, seed=7)
    even = bloom_for(10.0, 100.0, CELL, seed=8)
    assert odd.lean > 0 > even.lean            # mirror-image lean
    assert abs(odd.lean) == pytest.approx(abs(even.lean))
    assert abs(bloom_for(10.0, 100.0, CELL, 7).lean) > \
        abs(bloom_for(90.0, 100.0, CELL, 7).lean)


# --------------------------------------------------------------------------- #
# determinism                                                                  #
# --------------------------------------------------------------------------- #

def test_same_inputs_same_state():
    a = bloom_for(42.0, 130.0, CELL, seed=3)
    b = bloom_for(42.0, 130.0, CELL, seed=3)
    assert a == b


# --------------------------------------------------------------------------- #
# rendering                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def species_rows_loaded():
    return load_collections()


@pytest.mark.parametrize("sym", ["bayc", "punks", "azuki", "doodles",
                                 "moonbirds"])
@pytest.mark.parametrize("price,ath", [(100.0, 100.0), (12.0, 100.0),
                                       (0.4, 100.0), (0.0, 100.0)])
def test_render_returns_the_requested_canvas(species_rows_loaded, sym,
                                            price, ath):
    species = species_for(sym, species_rows_loaded)
    b = bloom_for(price, ath, CELL, seed=11)
    img = render_flower(CELL, species, b, seed=11)
    assert img.size == CELL
    assert img.mode == "RGBA"
    # something was actually painted: not a fully transparent frame
    assert img.getextrema()[3][1] == 255


@pytest.mark.parametrize("sym", ["bayc", "punks", "azuki", "doodles",
                                 "moonbirds"])
def test_render_is_deterministic(species_rows_loaded, sym):
    species = species_for(sym, species_rows_loaded)
    b = bloom_for(7.0, 60.0, CELL, seed=5)
    a = render_flower(CELL, species, b, seed=5)
    c = render_flower(CELL, species, b, seed=5)
    assert list(a.getdata()) == list(c.getdata())


def test_epitaph_renders_for_the_buried(species_rows_loaded):
    """When an epitaph is passed, the headstone must put ink on the frame."""
    species = species_for("moonbirds", species_rows_loaded)
    b = bloom_for(0.18, 22.0, CELL, seed=9)
    with_stone = render_flower(CELL, species, b, seed=9, epitaph="-99%")
    without = render_flower(CELL, species, b, seed=9, epitaph=None)
    assert list(with_stone.getdata()) != list(without.getdata())
    assert with_stone.size == CELL


def test_seed_changes_jitter_but_not_state(species_rows_loaded):
    """Different seeds scatter petals differently, same price same shape."""
    species = species_for("bayc", species_rows_loaded)
    b = bloom_for(50.0, 100.0, CELL, seed=1)
    a = render_flower(CELL, species, b, seed=1)
    c = render_flower(CELL, species, b, seed=2)
    assert list(a.getdata()) != list(c.getdata())
    assert bloom_for(50.0, 100.0, CELL, seed=1).ratio == \
        bloom_for(50.0, 100.0, CELL, seed=2).ratio


def test_log_scale_never_takes_log_of_a_nonpositive():
    """bloom_for must survive price=0 and ath=0 without math domain errors."""
    for price, ath in [(0, 0), (0, 10), (5, 0)]:
        b = bloom_for(price, ath, CELL, 0)
        assert math.isfinite(b.size) and math.isfinite(b.droop)
