"""FinViz Elite client for screener data."""

import os
import re
import csv
import logging
from datetime import datetime, timedelta
from typing import Optional
from io import StringIO
import requests

logger = logging.getLogger(__name__)


class FinVizClient:
    """Client for FinViz Elite screener."""

    BASE_URL = "https://elite.finviz.com"
    SCREENER_URL = "https://elite.finviz.com/screener.ashx"

    # Pre-built screener filters
    FILTERS = {
        'high_adr': 'ta_averagetruerange_o5',  # ATR > 5%
        'earnings_today': 'earningsdate_today',
        'earnings_tomorrow': 'earningsdate_tomorrow',
        'earnings_this_week': 'earningsdate_thisweek',
        'gap_up_5': 'ta_gap_u5',  # Gap up > 5%
        'gap_down_5': 'ta_gap_d5',  # Gap down > 5%
        'unusual_volume': 'sh_curvol_o2000',  # Volume > 2M
        'relative_volume_2x': 'sh_relvol_o2',  # Relative volume > 2x
        'overbought': 'ta_rsi_ob70',  # RSI > 70
        'oversold': 'ta_rsi_os30',  # RSI < 30
        'new_high': 'ta_newhigh',
        'new_low': 'ta_newlow',
        'above_sma50': 'ta_sma50_pa',
        'below_sma50': 'ta_sma50_pb',
        'above_sma200': 'ta_sma200_pa',
        'below_sma200': 'ta_sma200_pb',
        'price_above_10': 'sh_price_o10',
        'avg_vol_1m': 'sh_avgvol_o1000',  # Avg volume > 1M
        'mega_cap': 'cap_mega',
        'large_cap': 'cap_large',
        'mid_cap': 'cap_mid',
    }

    def __init__(self, session_cookie: Optional[str] = None):
        """
        Initialize FinViz client.

        Args:
            session_cookie: FinViz Elite session cookie for authenticated access.
                          Set FINVIZ_SESSION env var or pass directly.
        """
        self.session_cookie = session_cookie or os.environ.get('FINVIZ_SESSION')
        self.session = requests.Session()
        if self.session_cookie:
            self.session.cookies.set('screenerUrl', self.session_cookie)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _get_screener(self, filters: list, columns: str = "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20") -> list:
        """
        Run a screener query and return results.

        Args:
            filters: List of filter codes (from FILTERS dict)
            columns: Column selection for output

        Returns:
            List of dicts with stock data
        """
        filter_str = ','.join(filters)
        params = {
            'v': '152',  # Table view with all data
            'f': filter_str,
            'ft': '4',  # All stocks
            'o': '-change',  # Sort by change descending
            'c': columns
        }

        try:
            response = self.session.get(
                self.SCREENER_URL,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return self._parse_screener_html(response.text)
        except requests.RequestException as e:
            logger.error(f"FinViz screener error: {e}")
            return []

    def _parse_screener_html(self, html: str) -> list:
        """Parse screener HTML into structured data."""
        results = []

        # Simple regex parsing - FinViz HTML is consistent
        # Look for table rows with stock data
        ticker_pattern = r'<a[^>]*class="screener-link-primary"[^>]*>([A-Z]+)</a>'
        row_pattern = r'<tr[^>]*class="[^"]*screener[^"]*"[^>]*>(.*?)</tr>'

        for row_match in re.finditer(row_pattern, html, re.DOTALL):
            row_html = row_match.group(1)
            ticker_match = re.search(ticker_pattern, row_html)

            if ticker_match:
                ticker = ticker_match.group(1)
                # Extract numeric values from the row
                values = re.findall(r'>([+-]?\d+\.?\d*%?)</a>', row_html)

                # Basic structure - extend as needed
                result = {
                    'ticker': ticker,
                    'values': values
                }

                # Try to extract common fields
                change_match = re.search(r'>([+-]?\d+\.?\d+%)</span>', row_html)
                if change_match:
                    result['change'] = change_match.group(1)

                volume_match = re.search(r'>(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)</a>', row_html)
                if volume_match:
                    result['volume'] = volume_match.group(1)

                results.append(result)

        return results

    def get_earnings_today(self) -> list:
        """Get stocks with earnings today (before/after market)."""
        return self._get_screener([
            self.FILTERS['earnings_today'],
            self.FILTERS['price_above_10'],
            self.FILTERS['avg_vol_1m']
        ])

    def get_earnings_this_week(self) -> list:
        """Get stocks with earnings this week."""
        return self._get_screener([
            self.FILTERS['earnings_this_week'],
            self.FILTERS['price_above_10'],
            self.FILTERS['avg_vol_1m']
        ])

    def get_high_adr_stocks(self, min_price: float = 10) -> list:
        """Get stocks with high Average Daily Range (volatile movers)."""
        filters = [self.FILTERS['high_adr'], self.FILTERS['avg_vol_1m']]
        if min_price >= 10:
            filters.append(self.FILTERS['price_above_10'])
        results = self._get_screener(filters)
        # Ensure each result has a 'Ticker' key for scanner compatibility
        for result in results:
            if 'ticker' in result and 'Ticker' not in result:
                result['Ticker'] = result['ticker']
        return results

    def get_gap_ups(self, min_gap: float = 5) -> list:
        """Get stocks gapping up."""
        return self._get_screener([
            self.FILTERS['gap_up_5'],
            self.FILTERS['price_above_10'],
            self.FILTERS['avg_vol_1m']
        ])

    def get_gap_downs(self, min_gap: float = 5) -> list:
        """Get stocks gapping down."""
        return self._get_screener([
            self.FILTERS['gap_down_5'],
            self.FILTERS['price_above_10'],
            self.FILTERS['avg_vol_1m']
        ])

    def get_overbought(self) -> list:
        """Get stocks with RSI > 70 (overbought)."""
        return self._get_screener([
            self.FILTERS['overbought'],
            self.FILTERS['price_above_10'],
            self.FILTERS['avg_vol_1m']
        ])

    def get_oversold(self) -> list:
        """Get stocks with RSI < 30 (oversold)."""
        return self._get_screener([
            self.FILTERS['oversold'],
            self.FILTERS['price_above_10'],
            self.FILTERS['avg_vol_1m']
        ])

    def get_unusual_volume(self) -> list:
        """Get stocks with unusual volume (>2x average)."""
        return self._get_screener([
            self.FILTERS['relative_volume_2x'],
            self.FILTERS['price_above_10'],
            self.FILTERS['avg_vol_1m']
        ])

    def get_new_highs(self) -> list:
        """Get stocks at new 52-week highs."""
        return self._get_screener([
            self.FILTERS['new_high'],
            self.FILTERS['price_above_10'],
            self.FILTERS['avg_vol_1m']
        ])

    def get_new_lows(self) -> list:
        """Get stocks at new 52-week lows."""
        return self._get_screener([
            self.FILTERS['new_low'],
            self.FILTERS['price_above_10'],
            self.FILTERS['avg_vol_1m']
        ])

    def get_mega_caps(self) -> list:
        """Get mega cap stocks (>$200B market cap)."""
        return self._get_screener([
            self.FILTERS['mega_cap'],
            self.FILTERS['avg_vol_1m']
        ])

    # Combined scans for specific opportunity types

    def scan_earnings_reactions(self) -> dict:
        """
        Scan for earnings reaction setups.

        Returns:
            Dict with 'gap_ups' and 'gap_downs' that reported earnings
        """
        earnings = set()
        for stock in self.get_earnings_today():
            earnings.add(stock.get('ticker'))

        gap_ups = [s for s in self.get_gap_ups() if s.get('ticker') in earnings]
        gap_downs = [s for s in self.get_gap_downs() if s.get('ticker') in earnings]

        return {
            'gap_ups': gap_ups,
            'gap_downs': gap_downs
        }

    def scan_overextended(self) -> dict:
        """
        Scan for overextended stocks.

        Returns:
            Dict with 'overbought' and 'oversold' stocks with high volume
        """
        return {
            'overbought': self.get_overbought(),
            'oversold': self.get_oversold()
        }

    def scan_orb_candidates(self) -> list:
        """
        Get Opening Range Breakout candidates.

        High ADR stocks with volume are good ORB candidates.
        """
        return self.get_high_adr_stocks()

    def get_sector_etfs(self) -> dict:
        """Get major sector ETFs for sector rotation analysis."""
        return {
            'XLK': 'Technology',
            'XLF': 'Financials',
            'XLV': 'Health Care',
            'XLY': 'Consumer Discretionary',
            'XLC': 'Communication Services',
            'XLI': 'Industrials',
            'XLP': 'Consumer Staples',
            'XLE': 'Energy',
            'XLU': 'Utilities',
            'XLB': 'Materials',
            'XLRE': 'Real Estate'
        }

    def get_commodity_etfs(self) -> dict:
        """Get commodity ETFs for overextension scanning."""
        return {
            'GLD': 'Gold',
            'SLV': 'Silver',
            'USO': 'Oil',
            'UNG': 'Natural Gas',
            'COPX': 'Copper Miners',
            'WEAT': 'Wheat',
            'CORN': 'Corn',
            'DBA': 'Agriculture',
            'URA': 'Uranium'
        }

    def get_index_etfs(self) -> dict:
        """Get major index ETFs."""
        return {
            'SPY': 'S&P 500',
            'QQQ': 'NASDAQ 100',
            'IWM': 'Russell 2000',
            'DIA': 'Dow 30',
            'VTI': 'Total Market'
        }

    def get_leveraged_etfs(self) -> dict:
        """Get leveraged ETFs for aggressive plays."""
        return {
            'TQQQ': '3x NASDAQ Long',
            'SQQQ': '3x NASDAQ Short',
            'SPXL': '3x S&P Long',
            'SPXS': '3x S&P Short',
            'UVXY': '1.5x VIX Long',
            'SVXY': 'Short VIX',
            'TNA': '3x Russell Long',
            'TZA': '3x Russell Short'
        }

    # Convenience methods for scanner compatibility

    def get_earnings_calendar(self) -> list:
        """
        Get earnings calendar for this week.

        Returns list of dicts with 'Ticker' key for scanner compatibility.
        """
        results = self.get_earnings_this_week()
        # Ensure each result has a 'Ticker' key for scanner compatibility
        for result in results:
            if 'ticker' in result and 'Ticker' not in result:
                result['Ticker'] = result['ticker']
        return results

    def get_overextended_stocks(self, direction: str = "up") -> list:
        """
        Get overextended stocks by direction.

        Args:
            direction: "up" for overbought (RSI > 70), "down" for oversold (RSI < 30)

        Returns list of dicts with 'Ticker' key for scanner compatibility.
        """
        if direction.lower() == "up":
            results = self.get_overbought()
        else:
            results = self.get_oversold()

        # Ensure each result has a 'Ticker' key for scanner compatibility
        for result in results:
            if 'ticker' in result and 'Ticker' not in result:
                result['Ticker'] = result['ticker']
        return results
