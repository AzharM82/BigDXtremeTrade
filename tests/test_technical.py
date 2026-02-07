"""Tests for technical analysis calculations."""

import pytest
from src.utils.technical import (
    calc_atr, calc_sma, calc_ema, calc_rsi,
    calc_adr_pct, calc_consecutive_days,
    calc_relative_volume, calc_atr_multiple_from_ma,
    calc_vwap, calc_opening_range,
)


def _make_bars(closes, highs=None, lows=None, volumes=None):
    """Helper to create bar dicts from close prices."""
    n = len(closes)
    if highs is None:
        highs = [c * 1.01 for c in closes]
    if lows is None:
        lows = [c * 0.99 for c in closes]
    if volumes is None:
        volumes = [1000000] * n
    return [
        {"o": c, "h": h, "l": l, "c": c, "v": v}
        for c, h, l, v in zip(closes, highs, lows, volumes)
    ]


class TestSMA:
    def test_basic_sma(self):
        bars = _make_bars([10, 20, 30, 40, 50])
        assert calc_sma(bars, 5) == pytest.approx(30.0)

    def test_sma_uses_last_n(self):
        bars = _make_bars([5, 10, 20, 30, 40, 50])
        assert calc_sma(bars, 3) == pytest.approx(40.0)

    def test_sma_insufficient_data(self):
        bars = _make_bars([10, 20])
        assert calc_sma(bars, 5) == 0.0


class TestATR:
    def test_basic_atr(self):
        # Simple bars with known ranges
        bars = _make_bars(
            closes=[100, 102, 101, 104, 103, 106, 105, 108, 107, 110,
                    109, 112, 111, 114, 113, 116],
            highs= [101, 103, 102, 105, 104, 107, 106, 109, 108, 111,
                    110, 113, 112, 115, 114, 117],
            lows=  [99, 101, 100, 103, 102, 105, 104, 107, 106, 109,
                    108, 111, 110, 113, 112, 115],
        )
        atr = calc_atr(bars, 14)
        assert atr > 0

    def test_atr_insufficient_data(self):
        bars = _make_bars([100, 101])
        assert calc_atr(bars, 14) == 0.0


class TestRSI:
    def test_rsi_trending_up(self):
        # Monotonically increasing prices should give high RSI
        bars = _make_bars(list(range(50, 70)))
        rsi = calc_rsi(bars, 14)
        assert rsi > 70

    def test_rsi_trending_down(self):
        # Monotonically decreasing prices should give low RSI
        bars = _make_bars(list(range(70, 50, -1)))
        rsi = calc_rsi(bars, 14)
        assert rsi < 30

    def test_rsi_insufficient_data(self):
        bars = _make_bars([100, 101])
        assert calc_rsi(bars, 14) == 50.0


class TestConsecutiveDays:
    def test_up_streak(self):
        bars = _make_bars([10, 11, 12, 13, 14, 15])
        assert calc_consecutive_days(bars) == 5

    def test_down_streak(self):
        bars = _make_bars([15, 14, 13, 12, 11, 10])
        assert calc_consecutive_days(bars) == -5

    def test_mixed(self):
        bars = _make_bars([10, 11, 12, 11, 12, 13])
        # Last 2 bars are up
        assert calc_consecutive_days(bars) == 2


class TestATRMultiple:
    def test_overextended(self):
        multiple = calc_atr_multiple_from_ma(
            current_price=130, ma_value=100, atr=5
        )
        assert multiple == pytest.approx(6.0)

    def test_at_ma(self):
        multiple = calc_atr_multiple_from_ma(
            current_price=100, ma_value=100, atr=5
        )
        assert multiple == pytest.approx(0.0)


class TestVWAP:
    def test_basic_vwap(self):
        bars = [
            {"h": 101, "l": 99, "c": 100, "v": 1000},
            {"h": 103, "l": 101, "c": 102, "v": 2000},
        ]
        vwap = calc_vwap(bars)
        assert vwap > 0


class TestOpeningRange:
    def test_opening_range(self):
        bars = [
            {"h": 102, "l": 99, "c": 101, "v": 1000},
            {"h": 103, "l": 100, "c": 102, "v": 1000},
            {"h": 104, "l": 101, "c": 103, "v": 1000},
            {"h": 105, "l": 102, "c": 104, "v": 1000},
            {"h": 106, "l": 103, "c": 105, "v": 1000},
            {"h": 107, "l": 104, "c": 106, "v": 1000},
        ]
        or_high, or_low = calc_opening_range(bars, minutes=30, bar_size_min=5)
        assert or_high == 107  # Max high of first 6 bars
        assert or_low == 99    # Min low of first 6 bars
