"""
Earnings Reaction Reversal (ERR) Scanner.

Detects stocks that beat on earnings but gap down (or miss but gap up),
creating high-probability reversal opportunities.

Example: GOOG beats on Sales + EPS, drops at open, calls go from $3 to $6+.
"""

import logging
from datetime import datetime, timedelta

from src.data.polygon_client import PolygonClient
from src.data.finviz_client import FinVizClient
from src.models.opportunity import (
    Opportunity, OpportunityType, Direction, SignalStrength,
    EarningsData, Tradeplan, PriceLevel,
)
from src.utils.technical import (
    calc_atr, calc_sma, calc_vwap, calc_expected_move,
)
from config.settings import ScannerThresholds

logger = logging.getLogger(__name__)


class EarningsReversalScanner:
    """
    Scans for Earnings Reaction Reversal setups.

    The setup:
    1. Company beats on EPS and Revenue
    2. Stock gaps DOWN in pre-market (or vice versa for misses)
    3. The gap contradicts the fundamental result
    4. High pre-market volume confirms institutional attention
    5. IV crush makes the opposing option cheap

    Why it works:
    - Algos sell on headline keywords, missing context
    - Institutional repositioning takes hours, not seconds
    - The "wrong" gap gets bought aggressively once real analysis begins
    """

    def __init__(self, polygon: PolygonClient, finviz: FinVizClient,
                 thresholds: ScannerThresholds):
        self.polygon = polygon
        self.finviz = finviz
        self.thresholds = thresholds

    def scan(self, tickers: list[str] | None = None) -> list[Opportunity]:
        """
        Scan for ERR setups. If no tickers provided, uses earnings calendar.
        """
        opportunities = []

        if tickers is None:
            earnings_list = self.finviz.get_earnings_calendar()
            tickers = [row.get("Ticker", "") for row in earnings_list if row.get("Ticker")]

        for ticker in tickers:
            try:
                opp = self._analyze_ticker(ticker)
                if opp:
                    opportunities.append(opp)
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {e}")

        opportunities.sort(key=lambda o: o.score, reverse=True)
        return opportunities

    def _analyze_ticker(self, ticker: str) -> Opportunity | None:
        """Analyze a single ticker for ERR setup."""

        # Get earnings data
        financials = self.polygon.get_financials(ticker, limit=1)
        if not financials:
            return None

        # Get current snapshot for gap data
        snapshot = self.polygon.get_snapshot(ticker)
        if not snapshot:
            return None

        # Get daily bars for technical context
        today = datetime.now()
        from_date = (today - timedelta(days=60)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")
        bars = self.polygon.get_daily_bars(ticker, from_date, to_date)
        if len(bars) < 20:
            return None

        # Build earnings data
        earnings = self._build_earnings_data(ticker, financials[0], snapshot, bars)
        if not earnings:
            return None

        # Check if this is an ERR setup
        if not earnings.gap_contradicts_result:
            return None

        # Score the setup
        score, strength = self._score_setup(earnings, bars, snapshot)

        # Determine direction
        if earnings.is_beat and earnings.actual_gap_pct < 0:
            direction = Direction.LONG  # Beat + gap down = buy calls
        else:
            direction = Direction.SHORT  # Miss + gap up = buy puts

        # Build trade plan
        tradeplan = self._build_tradeplan(ticker, direction, bars, snapshot, earnings)

        # Build key levels
        key_levels = self._get_key_levels(bars, snapshot)

        headline = self._build_headline(ticker, earnings, direction)

        return Opportunity(
            ticker=ticker,
            opportunity_type=OpportunityType.ERR,
            direction=direction,
            signal_strength=strength,
            detected_at=datetime.now(),
            headline=headline,
            details={
                "eps_surprise_pct": earnings.eps_surprise_pct,
                "revenue_surprise_pct": earnings.revenue_surprise_pct,
                "actual_gap_pct": earnings.actual_gap_pct,
                "expected_move_pct": earnings.expected_move_pct,
                "gap_vs_expected": (
                    abs(earnings.actual_gap_pct or 0) / abs(earnings.expected_move_pct or 1)
                    if earnings.expected_move_pct else None
                ),
            },
            tradeplan=tradeplan,
            key_levels=key_levels,
            score=score,
        )

    def _build_earnings_data(self, ticker: str, financial: dict,
                             snapshot: dict, bars: list[dict]) -> EarningsData | None:
        """Extract earnings data from Polygon financials + snapshot."""
        try:
            # Extract EPS and revenue from financials
            income = financial.get("financials", {}).get("income_statement", {})
            eps_actual = income.get("basic_earnings_per_share", {}).get("value")
            revenue_actual = income.get("revenues", {}).get("value")

            # Get previous close and current for gap calculation
            prev_close = bars[-1]["c"] if bars else None
            current = snapshot.get("lastTrade", {}).get("p") or snapshot.get("day", {}).get("c")

            if not prev_close or not current:
                return None

            gap_pct = ((current - prev_close) / prev_close) * 100

            return EarningsData(
                ticker=ticker,
                report_date=financial.get("filing_date", ""),
                report_time="bmo",  # Will need to determine from calendar
                eps_actual=eps_actual,
                revenue_actual=revenue_actual,
                actual_gap_pct=gap_pct,
            )
        except (KeyError, TypeError) as e:
            logger.debug(f"Could not build earnings data for {ticker}: {e}")
            return None

    def _score_setup(self, earnings: EarningsData, bars: list[dict],
                     snapshot: dict) -> tuple[float, SignalStrength]:
        """Score the ERR setup from 0-100."""
        score = 0.0

        # EPS beat magnitude (0-25 points)
        eps_s = abs(earnings.eps_surprise_pct or 0)
        if eps_s > self.thresholds.err_eps_surprise_min:
            score += min(25, eps_s * 2.5)

        # Revenue beat magnitude (0-25 points)
        rev_s = abs(earnings.revenue_surprise_pct or 0)
        if rev_s > self.thresholds.err_revenue_surprise_min:
            score += min(25, rev_s * 5)

        # Gap size — larger contradictory gap = better opportunity (0-25 points)
        gap = abs(earnings.actual_gap_pct or 0)
        score += min(25, gap * 5)

        # Gap vs expected move — if actual gap is less than expected, extra upside (0-25 points)
        if earnings.expected_move_pct and gap < earnings.expected_move_pct:
            ratio = gap / earnings.expected_move_pct
            score += (1 - ratio) * 25

        # Determine signal strength
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
                         bars: list[dict], snapshot: dict,
                         earnings: EarningsData) -> Tradeplan:
        """Build a trade plan with entry, stop, and targets."""
        prev_close = bars[-1]["c"] if bars else 0
        atr = calc_atr(bars)
        current = snapshot.get("lastTrade", {}).get("p", prev_close)

        if direction == Direction.LONG:
            # Entry: reversal candle break (use current price as proxy)
            entry = current
            # Stop: below the gap low
            stop = current - (atr * 0.5)
            # T1: Fill the gap to previous close
            t1 = prev_close
            # T2: Previous close + expected move
            t2 = prev_close + atr
            # T3: Runner
            t3 = prev_close + (atr * 2)
        else:
            entry = current
            stop = current + (atr * 0.5)
            t1 = prev_close
            t2 = prev_close - atr
            t3 = prev_close - (atr * 2)

        return Tradeplan(
            entry_price=entry,
            stop_loss=stop,
            target_1=t1,
            target_2=t2,
            target_3=t3,
            direction=direction,
            max_risk_dollars=0,  # Set by risk manager based on account size
        )

    def _get_key_levels(self, bars: list[dict], snapshot: dict) -> list[PriceLevel]:
        """Identify key price levels for the trade."""
        levels = []

        if bars:
            sma_10 = calc_sma(bars, 10)
            sma_20 = calc_sma(bars, 20)
            sma_50 = calc_sma(bars, 50)
            prev_close = bars[-1]["c"]

            if sma_10:
                levels.append(PriceLevel(sma_10, "10 SMA", "ma"))
            if sma_20:
                levels.append(PriceLevel(sma_20, "20 SMA", "ma"))
            if sma_50:
                levels.append(PriceLevel(sma_50, "50 SMA", "ma"))
            levels.append(PriceLevel(prev_close, "Prev Close", "support"))

        return levels

    def _build_headline(self, ticker: str, earnings: EarningsData,
                        direction: Direction) -> str:
        action = "CALLS" if direction == Direction.LONG else "PUTS"
        beat_miss = "BEAT" if earnings.is_beat else "MISS"
        gap_dir = "down" if (earnings.actual_gap_pct or 0) < 0 else "up"
        return (
            f"[ERR] {ticker}: Earnings {beat_miss}, gapped {gap_dir} "
            f"{abs(earnings.actual_gap_pct or 0):.1f}% → {action} opportunity"
        )
