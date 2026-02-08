"""
Opening Range Breakout (ORB) Scanner.

Identifies high-ADR% stocks with tight opening ranges that are
breaking out with volume confirmation.

Best used in the first 30-60 minutes of the trading day.
"""

import logging
from datetime import datetime, timedelta

from src.data.polygon_client import PolygonClient
from src.data.finviz_client import FinVizClient
from src.models.opportunity import (
    Opportunity, OpportunityType, Direction, SignalStrength, Tradeplan, PriceLevel,
)
from src.utils.technical import (
    calc_atr, calc_adr_pct, calc_opening_range, calc_vwap, calc_sma,
)
from config.settings import ScannerThresholds

logger = logging.getLogger(__name__)


class ORBScanner:
    """
    Scans for Opening Range Breakout setups.

    Best for:
    - High ADR% stocks (>5%) that move enough to pay for options
    - Tight opening ranges (<50% of ADR) → coiled spring
    - Volume surge on breakout (>1.5x avg) → institutional participation
    - Aligned with market direction and RS rating
    """

    def __init__(self, polygon: PolygonClient, finviz: FinVizClient,
                 thresholds: ScannerThresholds):
        self.polygon = polygon
        self.finviz = finviz
        self.thresholds = thresholds

    def scan(self, tickers: list[str] | None = None) -> list[Opportunity]:
        """
        Scan for ORB setups. Best called after first 15-30 min of trading.
        """
        opportunities = []

        if tickers is None:
            # No watchlist provided — discover from FinViz + market movers
            try:
                high_adr = self.finviz.get_high_adr_stocks()
                tickers = [row.get("Ticker", "") for row in high_adr if row.get("Ticker")]
            except Exception:
                tickers = []

            # Augment with today's top movers (only in discovery mode)
            try:
                gainers = self.polygon.get_gainers_losers("gainers")
                losers = self.polygon.get_gainers_losers("losers")
                for item in (gainers + losers)[:20]:
                    t = item.get("ticker", "")
                    if t and t not in tickers:
                        tickers.append(t)
            except Exception as e:
                logger.warning(f"Could not fetch gainers/losers: {e}")

        for ticker in tickers:
            try:
                opp = self._analyze_ticker(ticker)
                if opp:
                    opportunities.append(opp)
            except Exception as e:
                logger.error(f"Error analyzing ORB for {ticker}: {e}")

        opportunities.sort(key=lambda o: o.score, reverse=True)
        return opportunities

    def _analyze_ticker(self, ticker: str) -> Opportunity | None:
        """Analyze a single ticker for ORB setup."""
        today = datetime.now()

        # Get daily bars for ADR% calculation
        from_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")
        daily_bars = self.polygon.get_daily_bars(ticker, from_date, to_date)
        if len(daily_bars) < 10:
            return None

        # Check ADR% threshold
        adr_pct = calc_adr_pct(daily_bars, 20)
        if adr_pct < self.thresholds.orb_adr_pct_min:
            return None

        # Get intraday 5-min bars for today
        today_str = today.strftime("%Y-%m-%d")
        intraday = self.polygon.get_intraday_bars(ticker, today_str, today_str, multiplier=5)
        if len(intraday) < 6:  # Need at least 30 min of data
            return None

        # Calculate opening range (first 30 min = 6 bars of 5-min)
        or_high, or_low = calc_opening_range(intraday, minutes=30, bar_size_min=5)
        or_range = or_high - or_low
        atr = calc_atr(daily_bars, 14)

        if atr == 0 or or_range == 0:
            return None

        # Check if opening range is tight relative to ADR
        or_range_pct = (or_range / daily_bars[-1]["c"]) * 100
        if or_range_pct > adr_pct * self.thresholds.orb_range_vs_adr_max:
            return None  # Opening range too wide

        # Check for breakout
        current = intraday[-1]["c"]
        vwap = calc_vwap(intraday)

        # Determine breakout direction
        if current > or_high:
            direction = Direction.LONG
            breakout = True
        elif current < or_low:
            direction = Direction.SHORT
            breakout = True
        else:
            return None  # Still inside range

        # Check volume confirmation
        recent_vol = sum(b["v"] for b in intraday[-3:]) / 3
        avg_vol = sum(b["v"] for b in intraday[:6]) / 6
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 0

        if vol_ratio < self.thresholds.orb_volume_breakout_multiple:
            return None  # No volume confirmation

        # Score the setup
        score = self._score_setup(adr_pct, or_range_pct, vol_ratio, current, vwap, direction)

        strength = (
            SignalStrength.STRONG if score >= 70
            else SignalStrength.MODERATE if score >= 50
            else SignalStrength.WEAK
        )

        # Build trade plan
        if direction == Direction.LONG:
            entry = current
            stop = or_low - (atr * 0.1)  # Just below OR low
            t1 = entry + or_range         # Measured move
            t2 = entry + (atr * 0.75)     # 75% of ATR
            t3 = entry + atr              # Full ATR
        else:
            entry = current
            stop = or_high + (atr * 0.1)
            t1 = entry - or_range
            t2 = entry - (atr * 0.75)
            t3 = entry - atr

        tradeplan = Tradeplan(
            entry_price=round(entry, 2),
            stop_loss=round(stop, 2),
            target_1=round(t1, 2),
            target_2=round(t2, 2),
            target_3=round(t3, 2),
            direction=direction,
        )

        key_levels = [
            PriceLevel(or_high, "OR High", "resistance"),
            PriceLevel(or_low, "OR Low", "support"),
            PriceLevel(vwap, "VWAP", "vwap"),
        ]

        action = "CALLS" if direction == Direction.LONG else "PUTS"
        return Opportunity(
            ticker=ticker,
            opportunity_type=OpportunityType.ORB,
            direction=direction,
            signal_strength=strength,
            detected_at=datetime.now(),
            headline=(
                f"[ORB] {ticker}: ADR {adr_pct:.1f}%, OR breakout "
                f"{'above' if direction == Direction.LONG else 'below'} "
                f"with {vol_ratio:.1f}x vol → {action}"
            ),
            details={
                "adr_pct": round(adr_pct, 2),
                "or_high": round(or_high, 2),
                "or_low": round(or_low, 2),
                "or_range_pct": round(or_range_pct, 2),
                "volume_ratio": round(vol_ratio, 2),
                "vwap": round(vwap, 2),
            },
            tradeplan=tradeplan,
            key_levels=key_levels,
            score=score,
        )

    def _score_setup(self, adr_pct: float, or_range_pct: float,
                     vol_ratio: float, current: float, vwap: float,
                     direction: Direction) -> float:
        score = 0.0

        # ADR% — higher = more potential (0-25)
        if adr_pct >= 10:
            score += 25
        elif adr_pct >= 7:
            score += 20
        elif adr_pct >= 5:
            score += 15

        # Tight OR relative to ADR (0-25)
        or_vs_adr = or_range_pct / adr_pct if adr_pct > 0 else 1
        if or_vs_adr < 0.25:
            score += 25
        elif or_vs_adr < 0.35:
            score += 20
        elif or_vs_adr < 0.50:
            score += 15

        # Volume surge (0-25)
        if vol_ratio >= 3.0:
            score += 25
        elif vol_ratio >= 2.0:
            score += 20
        elif vol_ratio >= 1.5:
            score += 15

        # VWAP alignment (0-25)
        if direction == Direction.LONG and current > vwap:
            score += 25
        elif direction == Direction.SHORT and current < vwap:
            score += 25

        return score
