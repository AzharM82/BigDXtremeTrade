"""
Momentum Scanner — Big Movers.

Identifies stocks with significant price moves:
- Up/Down 10%+ for the day
- Up/Down 20%+ for the week

These are momentum plays that often continue or reverse sharply.
"""

import logging
from datetime import datetime, timedelta

from src.data.polygon_client import PolygonClient
from src.data.finviz_client import FinVizClient
from src.models.opportunity import (
    Opportunity, OpportunityType, Direction, SignalStrength,
    Tradeplan, PriceLevel,
)
from src.utils.technical import calc_atr, calc_sma, calc_rsi, calc_relative_volume
from config.settings import ScannerThresholds

logger = logging.getLogger(__name__)


class MomentumScanner:
    """
    Scans for big movers — stocks with significant daily or weekly moves.

    Use cases:
    - Day movers (10%+): Momentum continuation or exhaustion reversal
    - Week movers (20%+): Trend confirmation or mean-reversion setup
    """

    def __init__(self, polygon: PolygonClient, finviz: FinVizClient,
                 thresholds: ScannerThresholds):
        self.polygon = polygon
        self.finviz = finviz
        self.thresholds = thresholds

    def scan_day_movers(self, min_move_pct: float = 10.0,
                        tickers: list[str] | None = None) -> dict:
        """
        Scan for stocks up or down 10%+ today.

        Returns dict with 'up' and 'down' lists of opportunities.
        """
        results = {'up': [], 'down': []}

        if tickers:
            # Watchlist mode: fetch all snapshots and filter to watchlist
            try:
                all_snapshots = self.polygon.get_snapshots_all()
                ticker_set = set(tickers)
                candidates = [s for s in all_snapshots if s.get('ticker', '') in ticker_set]
                logger.info(f"Day movers: matched {len(candidates)}/{len(tickers)} watchlist tickers from snapshots")
            except Exception as e:
                logger.error(f"Failed to fetch snapshots for watchlist: {e}")
                return results
        else:
            # Broad market mode: use top gainers/losers
            try:
                gainers = self.polygon.get_gainers_losers("gainers")
                losers = self.polygon.get_gainers_losers("losers")
                candidates = gainers + losers
            except Exception as e:
                logger.error(f"Failed to fetch gainers/losers: {e}")
                return results

        for item in candidates:
            ticker = item.get('ticker', '')
            if not ticker:
                continue

            try:
                change_pct = self._get_day_change_pct(item)
                if change_pct >= min_move_pct:
                    opp = self._build_day_mover_opportunity(
                        ticker, change_pct, Direction.LONG, item
                    )
                    if opp:
                        results['up'].append(opp)
                elif change_pct <= -min_move_pct:
                    opp = self._build_day_mover_opportunity(
                        ticker, change_pct, Direction.SHORT, item
                    )
                    if opp:
                        results['down'].append(opp)
            except Exception as e:
                logger.debug(f"Error processing {ticker}: {e}")

        # Sort by magnitude of move
        results['up'].sort(key=lambda o: o.details.get('change_pct', 0), reverse=True)
        results['down'].sort(key=lambda o: o.details.get('change_pct', 0))

        return results

    def scan_week_movers(self, min_move_pct: float = 20.0,
                         tickers: list[str] | None = None) -> dict:
        """
        Scan for stocks up or down 20%+ for the week.

        Returns dict with 'up' and 'down' lists of opportunities.
        """
        results = {'up': [], 'down': []}

        # Use provided tickers or scan all snapshots
        if tickers:
            scan_list = tickers
        else:
            # Get all snapshots and filter by weekly move
            try:
                all_tickers = self.polygon.get_snapshots_all()
                scan_list = [t.get('ticker', '') for t in all_tickers[:500] if t.get('ticker')]
            except Exception as e:
                logger.error(f"Failed to fetch snapshots: {e}")
                # Fall back to gainers/losers
                try:
                    gainers = self.polygon.get_gainers_losers("gainers")
                    losers = self.polygon.get_gainers_losers("losers")
                    scan_list = [t.get('ticker', '') for t in gainers + losers if t.get('ticker')]
                except Exception:
                    return results

        for ticker in scan_list:
            try:
                week_change = self._get_week_change_pct(ticker)
                if week_change is None:
                    continue

                if week_change >= min_move_pct:
                    opp = self._build_week_mover_opportunity(
                        ticker, week_change, Direction.LONG
                    )
                    if opp:
                        results['up'].append(opp)
                elif week_change <= -min_move_pct:
                    opp = self._build_week_mover_opportunity(
                        ticker, week_change, Direction.SHORT
                    )
                    if opp:
                        results['down'].append(opp)
            except Exception as e:
                logger.debug(f"Error processing {ticker} for weekly: {e}")

        # Sort by magnitude
        results['up'].sort(key=lambda o: o.details.get('week_change_pct', 0), reverse=True)
        results['down'].sort(key=lambda o: o.details.get('week_change_pct', 0))

        return results

    def scan_all(self, tickers: list[str] | None = None) -> dict:
        """
        Run all momentum scans.

        Returns dict with all categories.
        """
        day_movers = self.scan_day_movers(min_move_pct=10.0, tickers=tickers)
        week_movers = self.scan_week_movers(min_move_pct=20.0, tickers=tickers)

        return {
            'day_up_10': day_movers['up'],
            'day_down_10': day_movers['down'],
            'week_up_20': week_movers['up'],
            'week_down_20': week_movers['down'],
        }

    def _get_day_change_pct(self, snapshot: dict) -> float:
        """Extract day change percentage from snapshot."""
        # Polygon snapshot structure
        if 'todaysChangePerc' in snapshot:
            return float(snapshot['todaysChangePerc'])

        day = snapshot.get('day', {})
        prev = snapshot.get('prevDay', {})

        if day.get('c') and prev.get('c'):
            return ((day['c'] - prev['c']) / prev['c']) * 100

        return 0.0

    def _get_week_change_pct(self, ticker: str) -> float | None:
        """Calculate weekly change percentage for a ticker."""
        today = datetime.now()
        week_ago = today - timedelta(days=7)

        bars = self.polygon.get_daily_bars(
            ticker,
            week_ago.strftime('%Y-%m-%d'),
            today.strftime('%Y-%m-%d')
        )

        if len(bars) < 2:
            return None

        first_close = bars[0]['c']
        last_close = bars[-1]['c']

        if first_close == 0:
            return None

        return ((last_close - first_close) / first_close) * 100

    def _build_day_mover_opportunity(self, ticker: str, change_pct: float,
                                      direction: Direction,
                                      snapshot: dict) -> Opportunity | None:
        """Build opportunity for a day mover."""
        # Get additional data for scoring
        today = datetime.now()
        from_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        to_date = today.strftime('%Y-%m-%d')

        bars = self.polygon.get_daily_bars(ticker, from_date, to_date)
        if len(bars) < 5:
            return None

        atr = calc_atr(bars, 14)
        rsi = calc_rsi(bars, 14)
        rel_vol = calc_relative_volume(bars, 20)
        current = bars[-1]['c']

        # Score the setup
        score = self._score_day_mover(change_pct, rel_vol, rsi, direction)

        strength = (
            SignalStrength.EXTREME if score >= 80
            else SignalStrength.STRONG if score >= 60
            else SignalStrength.MODERATE if score >= 40
            else SignalStrength.WEAK
        )

        # Trade plan based on momentum or reversal
        if direction == Direction.LONG:
            # Momentum continuation
            entry = current
            stop = current - atr
            t1 = current + (atr * 0.5)
            t2 = current + atr
        else:
            entry = current
            stop = current + atr
            t1 = current - (atr * 0.5)
            t2 = current - atr

        tradeplan = Tradeplan(
            entry_price=round(entry, 2),
            stop_loss=round(stop, 2),
            target_1=round(t1, 2),
            target_2=round(t2, 2),
            direction=direction,
        )

        move_dir = "UP" if direction == Direction.LONG else "DOWN"
        action = "momentum CALLS" if direction == Direction.LONG else "momentum PUTS"

        return Opportunity(
            ticker=ticker,
            opportunity_type=OpportunityType.MOMENTUM,
            direction=direction,
            signal_strength=strength,
            detected_at=datetime.now(),
            headline=f"[DAY {move_dir}] {ticker}: {abs(change_pct):.1f}% today, "
                     f"RelVol {rel_vol:.1f}x → {action}",
            details={
                'change_pct': round(change_pct, 2),
                'relative_volume': round(rel_vol, 2),
                'rsi': round(rsi, 1),
                'atr': round(atr, 2),
                'scan_type': 'day_mover',
            },
            tradeplan=tradeplan,
            key_levels=[
                PriceLevel(calc_sma(bars, 20), "20 SMA", "ma"),
                PriceLevel(calc_sma(bars, 50), "50 SMA", "ma"),
            ],
            score=score,
        )

    def _build_week_mover_opportunity(self, ticker: str, week_change: float,
                                       direction: Direction) -> Opportunity | None:
        """Build opportunity for a week mover."""
        today = datetime.now()
        from_date = (today - timedelta(days=60)).strftime('%Y-%m-%d')
        to_date = today.strftime('%Y-%m-%d')

        bars = self.polygon.get_daily_bars(ticker, from_date, to_date)
        if len(bars) < 10:
            return None

        atr = calc_atr(bars, 14)
        rsi = calc_rsi(bars, 14)
        sma_20 = calc_sma(bars, 20)
        sma_50 = calc_sma(bars, 50)
        current = bars[-1]['c']

        # Score the setup
        score = self._score_week_mover(week_change, rsi, current, sma_20, sma_50, direction)

        strength = (
            SignalStrength.EXTREME if score >= 80
            else SignalStrength.STRONG if score >= 60
            else SignalStrength.MODERATE if score >= 40
            else SignalStrength.WEAK
        )

        # Trade plan
        if direction == Direction.LONG:
            entry = current
            stop = current - (atr * 1.5)
            t1 = current + atr
            t2 = current + (atr * 2)
        else:
            entry = current
            stop = current + (atr * 1.5)
            t1 = current - atr
            t2 = current - (atr * 2)

        tradeplan = Tradeplan(
            entry_price=round(entry, 2),
            stop_loss=round(stop, 2),
            target_1=round(t1, 2),
            target_2=round(t2, 2),
            direction=direction,
        )

        move_dir = "UP" if direction == Direction.LONG else "DOWN"
        action = "weekly momentum" if direction == Direction.LONG else "weekly breakdown"

        return Opportunity(
            ticker=ticker,
            opportunity_type=OpportunityType.MOMENTUM,
            direction=direction,
            signal_strength=strength,
            detected_at=datetime.now(),
            headline=f"[WEEK {move_dir}] {ticker}: {abs(week_change):.1f}% this week, "
                     f"RSI {rsi:.0f} → {action}",
            details={
                'week_change_pct': round(week_change, 2),
                'rsi': round(rsi, 1),
                'atr': round(atr, 2),
                'distance_from_20sma_pct': round((current - sma_20) / sma_20 * 100, 2) if sma_20 else 0,
                'scan_type': 'week_mover',
            },
            tradeplan=tradeplan,
            key_levels=[
                PriceLevel(sma_20, "20 SMA", "ma"),
                PriceLevel(sma_50, "50 SMA", "ma"),
            ],
            score=score,
        )

    def _score_day_mover(self, change_pct: float, rel_vol: float,
                          rsi: float, direction: Direction) -> float:
        """Score a day mover setup."""
        score = 0.0

        # Magnitude of move (0-30)
        magnitude = abs(change_pct)
        if magnitude >= 20:
            score += 30
        elif magnitude >= 15:
            score += 25
        elif magnitude >= 10:
            score += 20

        # Volume confirmation (0-30)
        if rel_vol >= 5.0:
            score += 30
        elif rel_vol >= 3.0:
            score += 25
        elif rel_vol >= 2.0:
            score += 20
        elif rel_vol >= 1.5:
            score += 15

        # RSI alignment (0-20)
        if direction == Direction.LONG and rsi > 60:
            score += 20
        elif direction == Direction.SHORT and rsi < 40:
            score += 20
        elif 40 <= rsi <= 60:
            score += 10  # Neutral RSI still valid

        # Momentum bonus for extreme moves (0-20)
        if magnitude >= 25:
            score += 20
        elif magnitude >= 20:
            score += 15
        elif magnitude >= 15:
            score += 10

        return min(100, score)

    def _score_week_mover(self, week_change: float, rsi: float,
                           current: float, sma_20: float, sma_50: float,
                           direction: Direction) -> float:
        """Score a week mover setup."""
        score = 0.0

        # Magnitude of weekly move (0-30)
        magnitude = abs(week_change)
        if magnitude >= 40:
            score += 30
        elif magnitude >= 30:
            score += 25
        elif magnitude >= 20:
            score += 20

        # RSI confirmation (0-25)
        if direction == Direction.LONG:
            if rsi > 70:
                score += 25  # Strong momentum
            elif rsi > 60:
                score += 20
            elif rsi > 50:
                score += 15
        else:
            if rsi < 30:
                score += 25
            elif rsi < 40:
                score += 20
            elif rsi < 50:
                score += 15

        # Price vs MAs alignment (0-25)
        if sma_20 and sma_50:
            if direction == Direction.LONG:
                if current > sma_20 > sma_50:
                    score += 25  # Bullish alignment
                elif current > sma_20:
                    score += 15
            else:
                if current < sma_20 < sma_50:
                    score += 25  # Bearish alignment
                elif current < sma_20:
                    score += 15

        # Trend strength bonus (0-20)
        if magnitude >= 50:
            score += 20
        elif magnitude >= 35:
            score += 15
        elif magnitude >= 25:
            score += 10

        return min(100, score)
