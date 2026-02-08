"""
Advanced Scanner Service - Wraps OpportunityEngine for web use.

Provides thread-safe access to ERR, OMR, Event Day, ORB, and Momentum scanners
with caching and JSON serialization.
"""

import csv
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from serializers import serialize_opportunity

logger = logging.getLogger(__name__)


class AdvancedScannerService:
    """Thread-safe wrapper around OpportunityEngine for web API use."""

    def __init__(self):
        self._lock = threading.Lock()
        self._engine = None
        self._cache: dict = {}
        self._last_scan_time: Optional[str] = None
        self._mainlist_tickers: list[str] = self._load_mainlist()

    def _load_mainlist(self) -> list[str]:
        """Load ticker symbols from mainlist.csv."""
        _dir = Path(__file__).parent
        mainlist_path = _dir / "mainlist.csv" if (_dir / "src").is_dir() else _dir.parent.parent / "mainlist.csv"
        tickers = []
        try:
            with open(mainlist_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('Ticker'):
                        tickers.append(row['Ticker'].strip())
            logger.info(f"AdvancedScannerService loaded {len(tickers)} mainlist tickers")
        except Exception as e:
            logger.error(f"Failed to load mainlist.csv: {e}")
        return tickers

    def _get_engine(self):
        """Lazy-init the OpportunityEngine."""
        if self._engine is None:
            from config.settings import AppConfig
            from src.scanners.opportunity_engine import OpportunityEngine
            config = AppConfig()
            self._engine = OpportunityEngine(config)
        return self._engine

    def run_weekly_prep(self) -> dict:
        """Run ERR, OMR, Event Day scanners (weekly prep)."""
        with self._lock:
            try:
                engine = self._get_engine()
                result = engine.run_weekly_prep(watchlist=self._mainlist_tickers)

                earnings = [serialize_opportunity(o) for o in result.get('earnings_week', [])]
                overextended = [serialize_opportunity(o) for o in result.get('overextended', [])]
                events = [serialize_opportunity(o) for o in result.get('events', [])]
                watchlist = [serialize_opportunity(o) for o in result.get('watchlist', [])]

                data = {
                    'earnings_reversal': earnings,
                    'overextension': overextended,
                    'event_day': events,
                    'watchlist': watchlist,
                    'scan_time': datetime.now().isoformat(),
                }

                self._cache['weekly_prep'] = data
                return data

            except Exception as e:
                logger.error(f"Weekly prep scan failed: {e}", exc_info=True)
                return {'error': str(e), 'earnings_reversal': [], 'overextension': [], 'event_day': [], 'watchlist': []}

    def run_orb_scan(self, tickers: list[str] = None) -> dict:
        """Run Opening Range Breakout scanner."""
        with self._lock:
            try:
                engine = self._get_engine()
                result = engine.run_orb_scan(tickers or self._mainlist_tickers)
                orb_opps = result if isinstance(result, list) else result.get('orb_opportunities', [])
                serialized = [serialize_opportunity(o) for o in orb_opps]

                data = {
                    'orb': serialized,
                    'scan_time': datetime.now().isoformat(),
                }

                self._cache['orb'] = data
                return data

            except Exception as e:
                logger.error(f"ORB scan failed: {e}", exc_info=True)
                return {'error': str(e), 'orb': []}

    def run_momentum_scan(self, tickers: list[str] = None) -> dict:
        """Run Momentum (big movers) scanner."""
        with self._lock:
            try:
                engine = self._get_engine()
                result = engine.run_momentum_scan(tickers or self._mainlist_tickers)

                momentum = {}
                for key in ('day_up_10', 'day_down_10', 'week_up_20', 'week_down_20'):
                    opps = result.get(key, [])
                    momentum[key] = [serialize_opportunity(o) for o in opps]

                data = {
                    'momentum': momentum,
                    'scan_time': datetime.now().isoformat(),
                }

                self._cache['momentum'] = data
                return data

            except Exception as e:
                logger.error(f"Momentum scan failed: {e}", exc_info=True)
                return {'error': str(e), 'momentum': {}}

    def run_all_advanced(self) -> dict:
        """Run all advanced scanners and cache combined results."""
        with self._lock:
            try:
                engine = self._get_engine()

                # Weekly prep (ERR + OMR + Events)
                weekly = engine.run_weekly_prep(watchlist=self._mainlist_tickers)
                earnings = [serialize_opportunity(o) for o in weekly.get('earnings_week', [])]
                overextended = [serialize_opportunity(o) for o in weekly.get('overextended', [])]
                events = [serialize_opportunity(o) for o in weekly.get('events', [])]

                # ORB scan
                orb_result = engine.run_orb_scan(self._mainlist_tickers)
                orb_opps = orb_result if isinstance(orb_result, list) else orb_result.get('orb_opportunities', [])
                orb = [serialize_opportunity(o) for o in orb_opps]

                # Momentum scan
                mom_result = engine.run_momentum_scan(self._mainlist_tickers)
                momentum = {}
                for key in ('day_up_10', 'day_down_10', 'week_up_20', 'week_down_20'):
                    opps = mom_result.get(key, [])
                    momentum[key] = [serialize_opportunity(o) for o in opps]

                # Top opportunities (all combined, sorted by score)
                all_opps = []
                all_opps.extend(weekly.get('earnings_week', []))
                all_opps.extend(weekly.get('overextended', []))
                all_opps.extend(weekly.get('events', []))
                all_opps.extend(orb_opps)
                for key in ('day_up_10', 'day_down_10', 'week_up_20', 'week_down_20'):
                    all_opps.extend(mom_result.get(key, []))

                all_opps.sort(key=lambda o: o.score, reverse=True)
                top = [serialize_opportunity(o) for o in all_opps[:20]]

                scan_time = datetime.now().isoformat()
                data = {
                    'earnings_reversal': earnings,
                    'overextension': overextended,
                    'event_day': events,
                    'orb': orb,
                    'momentum': momentum,
                    'top_opportunities': top,
                    'scan_time': scan_time,
                    'total_opportunities': len(earnings) + len(overextended) + len(events) + len(orb) + sum(len(v) for v in momentum.values()),
                }

                self._cache['all'] = data
                self._last_scan_time = scan_time
                return data

            except Exception as e:
                logger.error(f"Advanced scan failed: {e}", exc_info=True)
                return {
                    'error': str(e),
                    'earnings_reversal': [],
                    'overextension': [],
                    'event_day': [],
                    'orb': [],
                    'momentum': {},
                    'top_opportunities': [],
                    'scan_time': None,
                    'total_opportunities': 0,
                }

    def get_cached_results(self) -> dict:
        """Return cached results or empty structure."""
        if 'all' in self._cache:
            return self._cache['all']
        return {
            'earnings_reversal': [],
            'overextension': [],
            'event_day': [],
            'orb': [],
            'momentum': {},
            'top_opportunities': [],
            'scan_time': None,
            'total_opportunities': 0,
            'message': 'No advanced scan results available. Run a scan first.',
        }

    def get_top_opportunities(self, limit: int = 20) -> list:
        """Return top opportunities from cache, sorted by score."""
        cached = self.get_cached_results()
        return cached.get('top_opportunities', [])[:limit]
