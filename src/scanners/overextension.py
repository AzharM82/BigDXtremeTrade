"""
Overextension Mean-Reversion (OMR) Scanner.

Detects stocks/ETFs that are stretched far beyond their moving averages,
signaling high-probability mean-reversion trades.

Example: SLV at 10x ATR from 50MA with declining volume → PUT opportunity.
"""

import logging
from datetime import datetime, timedelta

from src.data.polygon_client import PolygonClient
from src.data.finviz_client import FinVizClient
from src.models.opportunity import (
    Opportunity, OpportunityType, Direction, SignalStrength,
    ExtensionData, Tradeplan, PriceLevel,
)
from src.utils.technical import (
    calc_atr, calc_sma, calc_rsi, calc_consecutive_days,
    calc_relative_volume, find_52w_high_low, calc_atr_multiple_from_ma,
)
from config.settings import ScannerThresholds

logger = logging.getLogger(__name__)

# Major ETFs and commodities to always scan for OMR
ALWAYS_SCAN = [
    # Commodity ETFs
    "SLV", "GLD", "USO", "UNG", "COPX", "WEAT",
    # Index ETFs
    "SPY", "QQQ", "IWM", "DIA",
    # Sector ETFs
    "XLF", "XLE", "XLK", "XLV", "XLI", "XLU", "XLC", "XLRE",
    # Volatility
    "VIX",
    # Leveraged (for confirmation)
    "TQQQ", "SQQQ", "UVXY",
]


class OverextensionScanner:
    """
    Scans for Overextension Mean-Reversion setups.

    The setup:
    1. Price is >5x ATR from 50MA (extreme stretch)
    2. 5+ consecutive days in one direction
    3. Volume declining on last 2 days (exhaustion)
    4. RSI extreme (>80 or <20)
    5. Futures/pre-market signaling reversal

    Why it works:
    - Mean reversion is the strongest force in markets
    - Extended moves attract late buyers who become forced sellers
    - The snap-back is violent because stops are all clustered
    - Options premiums are inflated on the trend side, cheap on reversal side
    """

    def __init__(self, polygon: PolygonClient, finviz: FinVizClient,
                 thresholds: ScannerThresholds):
        self.polygon = polygon
        self.finviz = finviz
        self.thresholds = thresholds

    def scan(self, tickers: list[str] | None = None) -> list[Opportunity]:
        """Scan for OMR setups across given tickers + always-scan list."""
        opportunities = []

        scan_list = list(set((tickers or []) + ALWAYS_SCAN))

        # Also pull overextended stocks from FinViz
        try:
            finviz_up = self.finviz.get_overextended_stocks("up")
            finviz_down = self.finviz.get_overextended_stocks("down")
            for row in finviz_up + finviz_down:
                t = row.get("Ticker", "")
                if t and t not in scan_list:
                    scan_list.append(t)
        except Exception as e:
            logger.warning(f"FinViz overextended scan failed: {e}")

        for ticker in scan_list:
            try:
                opp = self._analyze_ticker(ticker)
                if opp:
                    opportunities.append(opp)
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {e}")

        opportunities.sort(key=lambda o: o.score, reverse=True)
        return opportunities

    def _analyze_ticker(self, ticker: str) -> Opportunity | None:
        """Analyze a single ticker for OMR setup."""
        today = datetime.now()
        from_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")

        bars = self.polygon.get_daily_bars(ticker, from_date, to_date)
        if len(bars) < 60:
            return None

        # Calculate all metrics
        ext = self._build_extension_data(ticker, bars)
        if not ext:
            return None

        # Check if overextended
        if not ext.is_overextended_up and not ext.is_overextended_down:
            return None

        # Check minimum ATR multiple threshold
        if ext.atr_multiple_from_ma < self.thresholds.omr_atr_multiple_from_ma:
            return None

        # Score and classify
        score, strength = self._score_setup(ext)

        # Direction is OPPOSITE the extension (mean reversion)
        if ext.is_overextended_up:
            direction = Direction.SHORT  # Buy puts on overextended up
        else:
            direction = Direction.LONG   # Buy calls on overextended down

        # Build trade plan
        tradeplan = self._build_tradeplan(ticker, direction, ext, bars)
        key_levels = self._get_key_levels(ext, bars)
        headline = self._build_headline(ticker, ext, direction)

        return Opportunity(
            ticker=ticker,
            opportunity_type=OpportunityType.OMR,
            direction=direction,
            signal_strength=strength,
            detected_at=datetime.now(),
            headline=headline,
            details={
                "atr_multiple_from_50ma": round(ext.atr_multiple_from_ma, 2),
                "rsi_14": round(ext.rsi_14, 1),
                "consecutive_days": ext.consecutive_days,
                "relative_volume": round(ext.relative_volume, 2),
                "distance_from_52w_high_pct": round(ext.distance_from_52w_high_pct, 2),
                "distance_from_52w_low_pct": round(ext.distance_from_52w_low_pct, 2),
                "current_price": ext.current_price,
                "ma_50": round(ext.ma_50, 2),
                "atr_14": round(ext.atr_14, 2),
            },
            tradeplan=tradeplan,
            key_levels=key_levels,
            score=score,
        )

    def _build_extension_data(self, ticker: str, bars: list[dict]) -> ExtensionData | None:
        """Build ExtensionData from daily bars."""
        try:
            current_price = bars[-1]["c"]
            ma_50 = calc_sma(bars, 50)
            atr_14 = calc_atr(bars, 14)
            rsi_14 = calc_rsi(bars, 14)
            consecutive = calc_consecutive_days(bars)
            rel_vol = calc_relative_volume(bars, 20)
            high_52w, low_52w = find_52w_high_low(bars[-252:] if len(bars) >= 252 else bars)

            dist_high = ((current_price - high_52w) / high_52w * 100) if high_52w else 0
            dist_low = ((current_price - low_52w) / low_52w * 100) if low_52w else 0

            avg_dollar_vol = sum(
                b["c"] * b["v"] for b in bars[-20:]
            ) / min(20, len(bars[-20:]))

            return ExtensionData(
                ticker=ticker,
                current_price=current_price,
                ma_50=ma_50,
                atr_14=atr_14,
                rsi_14=rsi_14,
                consecutive_days=consecutive,
                distance_from_52w_high_pct=dist_high,
                distance_from_52w_low_pct=dist_low,
                relative_volume=rel_vol,
                avg_dollar_volume=avg_dollar_vol,
            )
        except (KeyError, ZeroDivisionError) as e:
            logger.debug(f"Could not build extension data for {ticker}: {e}")
            return None

    def _score_setup(self, ext: ExtensionData) -> tuple[float, SignalStrength]:
        """Score the OMR setup from 0-100."""
        score = 0.0

        # ATR multiple from MA (0-30 points) — the core signal
        atr_mult = ext.atr_multiple_from_ma
        if atr_mult >= 10:
            score += 30
        elif atr_mult >= 7:
            score += 25
        elif atr_mult >= 5:
            score += 15

        # RSI extreme (0-20 points)
        if ext.rsi_14 >= 85 or ext.rsi_14 <= 15:
            score += 20
        elif ext.rsi_14 >= 80 or ext.rsi_14 <= 20:
            score += 15
        elif ext.rsi_14 >= 75 or ext.rsi_14 <= 25:
            score += 10

        # Consecutive days (0-20 points)
        consec = abs(ext.consecutive_days)
        if consec >= 8:
            score += 20
        elif consec >= 6:
            score += 15
        elif consec >= 5:
            score += 10

        # Volume exhaustion — declining volume is bearish for the trend (0-15 points)
        if ext.relative_volume < 0.7:
            score += 15
        elif ext.relative_volume < 0.85:
            score += 10

        # Near 52-week extreme (0-15 points)
        if abs(ext.distance_from_52w_high_pct) < 2 or abs(ext.distance_from_52w_low_pct) < 5:
            score += 15
        elif abs(ext.distance_from_52w_high_pct) < 5 or abs(ext.distance_from_52w_low_pct) < 10:
            score += 10

        # Strength classification
        if score >= 75:
            strength = SignalStrength.EXTREME
        elif score >= 55:
            strength = SignalStrength.STRONG
        elif score >= 35:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        return score, strength

    def _build_tradeplan(self, ticker: str, direction: Direction,
                         ext: ExtensionData, bars: list[dict]) -> Tradeplan:
        """Build mean-reversion trade plan."""
        sma_20 = calc_sma(bars, 20)

        if direction == Direction.SHORT:
            # Fading the uptrend — buying puts
            entry = ext.current_price
            stop = ext.current_price + ext.atr_14  # 1 ATR above current
            t1 = sma_20                             # First target: 20MA
            t2 = ext.ma_50                          # Second target: 50MA
            t3 = ext.ma_50 - ext.atr_14             # Overshoot below 50MA
        else:
            # Fading the downtrend — buying calls
            entry = ext.current_price
            stop = ext.current_price - ext.atr_14
            t1 = sma_20
            t2 = ext.ma_50
            t3 = ext.ma_50 + ext.atr_14

        return Tradeplan(
            entry_price=round(entry, 2),
            stop_loss=round(stop, 2),
            target_1=round(t1, 2),
            target_2=round(t2, 2),
            target_3=round(t3, 2),
            direction=direction,
        )

    def _get_key_levels(self, ext: ExtensionData, bars: list[dict]) -> list[PriceLevel]:
        levels = [
            PriceLevel(ext.ma_50, "50 SMA", "ma"),
            PriceLevel(calc_sma(bars, 20), "20 SMA", "ma"),
            PriceLevel(calc_sma(bars, 10), "10 SMA", "ma"),
        ]

        high_52w, low_52w = find_52w_high_low(bars[-252:] if len(bars) >= 252 else bars)
        if high_52w:
            levels.append(PriceLevel(high_52w, "52W High", "resistance"))
        if low_52w:
            levels.append(PriceLevel(low_52w, "52W Low", "support"))

        return levels

    def _build_headline(self, ticker: str, ext: ExtensionData,
                        direction: Direction) -> str:
        action = "PUTS" if direction == Direction.SHORT else "CALLS"
        trend = "UP" if ext.is_overextended_up else "DOWN"
        return (
            f"[OMR] {ticker}: {ext.atr_multiple_from_ma:.1f}x ATR from 50MA, "
            f"RSI {ext.rsi_14:.0f}, {abs(ext.consecutive_days)} days {trend} → {action}"
        )
