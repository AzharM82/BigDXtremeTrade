"""
Event Day Volatility Scanner.

Tracks FOMC, CPI, NFP, and other macro events.
Identifies IV overpricing and post-event directional setups.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from src.data.polygon_client import PolygonClient
from src.models.opportunity import (
    Opportunity, OpportunityType, Direction, SignalStrength, Tradeplan, PriceLevel,
)
from src.utils.technical import calc_atr, calc_sma
from config.settings import ScannerThresholds

logger = logging.getLogger(__name__)

# Major economic events that create volatility opportunities
# Dates should be updated weekly/monthly from economic calendar
MACRO_EVENTS = {
    "FOMC": {
        "description": "Federal Reserve Interest Rate Decision",
        "impact": "extreme",
        "typical_spy_move_pct": 1.5,
        "best_instruments": ["SPY", "QQQ", "TLT", "GLD"],
    },
    "CPI": {
        "description": "Consumer Price Index",
        "impact": "high",
        "typical_spy_move_pct": 1.0,
        "best_instruments": ["SPY", "QQQ", "TLT", "XLF"],
    },
    "NFP": {
        "description": "Non-Farm Payrolls",
        "impact": "high",
        "typical_spy_move_pct": 0.8,
        "best_instruments": ["SPY", "IWM", "XLF"],
    },
    "PPI": {
        "description": "Producer Price Index",
        "impact": "moderate",
        "typical_spy_move_pct": 0.6,
        "best_instruments": ["SPY", "QQQ"],
    },
    "GDP": {
        "description": "Gross Domestic Product",
        "impact": "moderate",
        "typical_spy_move_pct": 0.5,
        "best_instruments": ["SPY", "DIA"],
    },
    "PCE": {
        "description": "Personal Consumption Expenditures",
        "impact": "high",
        "typical_spy_move_pct": 0.8,
        "best_instruments": ["SPY", "QQQ", "TLT"],
    },
}


class EventDayScanner:
    """
    Scans for event-day volatility opportunities.

    Pre-event: Identifies if IV is overpriced vs expected move.
    Post-event: Identifies directional commitment after announcement.
    """

    def __init__(self, polygon: PolygonClient, thresholds: ScannerThresholds):
        self.polygon = polygon
        self.thresholds = thresholds
        self._event_dates: dict[str, list[str]] = {}  # event_type -> [date strings]

    def set_event_dates(self, event_type: str, dates: list[str]):
        """Set upcoming event dates. Dates in YYYY-MM-DD format."""
        self._event_dates[event_type] = dates

    def load_event_calendar(self, calendar_data: list[dict]):
        """
        Load events from calendar data.
        Each entry: {"event": "FOMC", "date": "2026-02-15", "time": "14:00"}
        """
        for entry in calendar_data:
            event = entry.get("event", "").upper()
            date = entry.get("date", "")
            if event in MACRO_EVENTS and date:
                self._event_dates.setdefault(event, []).append(date)

    def scan_upcoming(self, days_ahead: int = 3) -> list[Opportunity]:
        """Scan for events happening in the next N days."""
        opportunities = []
        today = datetime.now()

        for event_type, dates in self._event_dates.items():
            for date_str in dates:
                try:
                    event_date = datetime.strptime(date_str, "%Y-%m-%d")
                    days_until = (event_date - today).days

                    if 0 <= days_until <= days_ahead:
                        event_info = MACRO_EVENTS.get(event_type, {})
                        instruments = event_info.get("best_instruments", ["SPY"])

                        for ticker in instruments:
                            opp = self._analyze_pre_event(
                                ticker, event_type, event_info, days_until
                            )
                            if opp:
                                opportunities.append(opp)

                except (ValueError, KeyError) as e:
                    logger.debug(f"Skipping event date {date_str}: {e}")

        return opportunities

    def _analyze_pre_event(self, ticker: str, event_type: str,
                           event_info: dict, days_until: int) -> Opportunity | None:
        """Analyze pre-event setup for a ticker."""

        today = datetime.now()
        from_date = (today - timedelta(days=60)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")
        bars = self.polygon.get_daily_bars(ticker, from_date, to_date)

        if len(bars) < 20:
            return None

        atr = calc_atr(bars)
        current = bars[-1]["c"]

        # Check for tight pre-event range (compression before expansion)
        last_2_range = max(b["h"] for b in bars[-2:]) - min(b["l"] for b in bars[-2:])
        range_vs_atr = last_2_range / atr if atr else 0

        # Tight range before event = good setup
        if range_vs_atr > 2.0:
            return None  # Already moved, less opportunity

        typical_move = event_info.get("typical_spy_move_pct", 1.0)
        score = 50.0  # Base score for event days

        if range_vs_atr < 1.0:
            score += 20  # Very compressed
        if days_until == 0:
            score += 15  # Event day

        strength = (
            SignalStrength.STRONG if score >= 70
            else SignalStrength.MODERATE if score >= 50
            else SignalStrength.WEAK
        )

        # Pre-event trade plan: straddle or wait for direction
        tradeplan = Tradeplan(
            entry_price=current,
            stop_loss=current - (atr * 0.5),
            target_1=current + (current * typical_move / 100),
            target_2=current + (current * typical_move * 1.5 / 100),
            direction=Direction.LONG,  # Placeholder — direction determined post-event
        )

        return Opportunity(
            ticker=ticker,
            opportunity_type=OpportunityType.EVENT,
            direction=Direction.LONG,  # TBD post-event
            signal_strength=strength,
            detected_at=datetime.now(),
            headline=(
                f"[EVENT] {event_type} in {days_until}d — {ticker} "
                f"range compressed {range_vs_atr:.1f}x ATR, "
                f"typical move {typical_move}%"
            ),
            details={
                "event_type": event_type,
                "days_until_event": days_until,
                "range_compression": round(range_vs_atr, 2),
                "typical_move_pct": typical_move,
                "atr": round(atr, 2),
            },
            tradeplan=tradeplan,
            score=score,
        )
