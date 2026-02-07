"""
Technical analysis calculations.
All functions work on lists of OHLCV bar dicts from Polygon.io.
"""

import math
from typing import Optional


def calc_atr(bars: list[dict], period: int = 14) -> float:
    """Calculate Average True Range from OHLCV bars."""
    if len(bars) < period + 1:
        return 0.0

    true_ranges = []
    for i in range(1, len(bars)):
        high = bars[i]["h"]
        low = bars[i]["l"]
        prev_close = bars[i - 1]["c"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    # Use simple average for initial ATR, then EMA-style
    if len(true_ranges) < period:
        return sum(true_ranges) / len(true_ranges)

    atr = sum(true_ranges[:period]) / period
    for tr in true_ranges[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def calc_sma(bars: list[dict], period: int, field: str = "c") -> float:
    """Calculate Simple Moving Average."""
    if len(bars) < period:
        return 0.0
    values = [b[field] for b in bars[-period:]]
    return sum(values) / period


def calc_ema(bars: list[dict], period: int, field: str = "c") -> float:
    """Calculate Exponential Moving Average."""
    if len(bars) < period:
        return 0.0

    multiplier = 2 / (period + 1)
    ema = sum(b[field] for b in bars[:period]) / period

    for bar in bars[period:]:
        ema = (bar[field] - ema) * multiplier + ema
    return ema


def calc_rsi(bars: list[dict], period: int = 14) -> float:
    """Calculate Relative Strength Index."""
    if len(bars) < period + 1:
        return 50.0  # neutral default

    changes = [bars[i]["c"] - bars[i - 1]["c"] for i in range(1, len(bars))]

    gains = [c if c > 0 else 0 for c in changes[:period]]
    losses = [-c if c < 0 else 0 for c in changes[:period]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    for c in changes[period:]:
        gain = c if c > 0 else 0
        loss = -c if c < 0 else 0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_adr_pct(bars: list[dict], period: int = 20) -> float:
    """Calculate Average Daily Range as percentage."""
    if len(bars) < period:
        return 0.0
    recent = bars[-period:]
    ranges = [(b["h"] - b["l"]) / b["c"] * 100 for b in recent if b["c"] > 0]
    return sum(ranges) / len(ranges) if ranges else 0.0


def calc_consecutive_days(bars: list[dict]) -> int:
    """
    Count consecutive up or down close days from most recent.
    Returns positive for up streaks, negative for down streaks.
    """
    if len(bars) < 2:
        return 0

    count = 0
    for i in range(len(bars) - 1, 0, -1):
        if bars[i]["c"] > bars[i - 1]["c"]:
            if count <= 0 and count != 0:
                break
            count += 1
        elif bars[i]["c"] < bars[i - 1]["c"]:
            if count >= 0 and count != 0:
                break
            count -= 1
        else:
            break

    return count


def calc_relative_volume(bars: list[dict], avg_period: int = 20) -> float:
    """Calculate current volume relative to average."""
    if len(bars) < avg_period + 1:
        return 1.0
    avg_vol = sum(b["v"] for b in bars[-(avg_period + 1):-1]) / avg_period
    if avg_vol == 0:
        return 0.0
    return bars[-1]["v"] / avg_vol


def calc_distance_from_ma(current_price: float, ma_value: float) -> float:
    """Calculate percentage distance from a moving average."""
    if ma_value == 0:
        return 0.0
    return ((current_price - ma_value) / ma_value) * 100


def calc_atr_multiple_from_ma(current_price: float, ma_value: float, atr: float) -> float:
    """Calculate how many ATRs the price is from the MA."""
    if atr == 0:
        return 0.0
    return abs(current_price - ma_value) / atr


def find_52w_high_low(bars: list[dict]) -> tuple[float, float]:
    """Find 52-week high and low from daily bars (need ~252 bars)."""
    if not bars:
        return 0.0, 0.0
    high = max(b["h"] for b in bars)
    low = min(b["l"] for b in bars)
    return high, low


def calc_expected_move(atm_call_price: float, atm_put_price: float,
                       stock_price: float) -> float:
    """
    Calculate expected move from ATM straddle price.
    Expected Move = Straddle Price * 0.85 (rule of thumb).
    Returns as percentage.
    """
    if stock_price == 0:
        return 0.0
    straddle = atm_call_price + atm_put_price
    expected_move = straddle * 0.85
    return (expected_move / stock_price) * 100


def calc_vwap(bars: list[dict]) -> float:
    """Calculate VWAP from intraday bars."""
    if not bars:
        return 0.0
    cumulative_tp_vol = 0.0
    cumulative_vol = 0.0
    for b in bars:
        typical_price = (b["h"] + b["l"] + b["c"]) / 3
        cumulative_tp_vol += typical_price * b["v"]
        cumulative_vol += b["v"]
    if cumulative_vol == 0:
        return 0.0
    return cumulative_tp_vol / cumulative_vol


def calc_opening_range(bars: list[dict], minutes: int = 30, bar_size_min: int = 5) -> tuple[float, float]:
    """
    Calculate opening range high/low from intraday bars.
    Returns (range_high, range_low).
    """
    num_bars = minutes // bar_size_min
    if len(bars) < num_bars:
        num_bars = len(bars)
    or_bars = bars[:num_bars]
    if not or_bars:
        return 0.0, 0.0
    return max(b["h"] for b in or_bars), min(b["l"] for b in or_bars)
