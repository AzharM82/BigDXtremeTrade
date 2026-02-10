"""Polygon.io API client for market data."""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
import requests

logger = logging.getLogger(__name__)


class PolygonClient:
    """Client for Polygon.io REST API."""

    BASE_URL = "https://api.polygon.io"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('POLYGON_API_KEY')
        if not self.api_key:
            raise ValueError("POLYGON_API_KEY not set")
        self.session = requests.Session()
        self._last_request_time = 0
        self._min_request_interval = 0.25  # 4 requests/second max

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make GET request to Polygon API."""
        self._rate_limit()
        params = params or {}
        params['apiKey'] = self.api_key
        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Polygon API error: {e}")
            return {}

    def get_snapshot(self, ticker: str) -> dict:
        """Get current snapshot for a ticker (price, volume, change)."""
        data = self._get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}")
        return data.get('ticker', {})

    def get_snapshots_all(self) -> list:
        """Get snapshots for all tickers (useful for broad scans)."""
        data = self._get("/v2/snapshot/locale/us/markets/stocks/tickers")
        return data.get('tickers', [])

    def get_previous_close(self, ticker: str) -> dict:
        """Get previous day's OHLCV."""
        data = self._get(f"/v2/aggs/ticker/{ticker}/prev")
        results = data.get('results', [])
        return results[0] if results else {}

    def get_daily_bars(
        self,
        ticker: str,
        from_date: str,
        to_date: str,
        adjusted: bool = True,
        limit: int = 5000
    ) -> list:
        """
        Get daily OHLCV bars for a ticker.

        Args:
            ticker: Stock symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            adjusted: Whether to adjust for splits/dividends
            limit: Max results
        """
        data = self._get(
            f"/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}",
            params={'adjusted': str(adjusted).lower(), 'sort': 'asc', 'limit': limit}
        )
        return data.get('results', [])

    def get_intraday_bars(
        self,
        ticker: str,
        from_date: str,
        to_date: str,
        multiplier: int = 5,
        timespan: str = "minute",
        limit: int = 5000
    ) -> list:
        """
        Get intraday bars for a ticker.

        Args:
            ticker: Stock symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            multiplier: Bar size multiplier
            timespan: minute, hour, day, week, month
            limit: Max results
        """
        data = self._get(
            f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
            params={'adjusted': 'true', 'sort': 'asc', 'limit': limit}
        )
        return data.get('results', [])

    def get_grouped_daily(self, date: str) -> list:
        """Get all tickers' daily bars for a specific date."""
        data = self._get(f"/v2/aggs/grouped/locale/us/market/stocks/{date}")
        return data.get('results', [])

    def get_ticker_details(self, ticker: str) -> dict:
        """Get company details (name, sector, market cap, etc.)."""
        data = self._get(f"/v3/reference/tickers/{ticker}")
        return data.get('results', {})

    def get_financials(self, ticker: str, limit: int = 4) -> list:
        """Get quarterly financials for a ticker."""
        data = self._get(
            f"/vX/reference/financials",
            params={'ticker': ticker, 'limit': limit}
        )
        return data.get('results', [])

    def get_earnings(self, ticker: str = None, date: str = None) -> list:
        """
        Get earnings data.

        Args:
            ticker: Filter by specific ticker
            date: Filter by report date (YYYY-MM-DD)
        """
        params = {}
        if ticker:
            params['ticker'] = ticker
        if date:
            params['report_date'] = date

        # Note: Polygon's earnings endpoint may need different access
        # This is a placeholder - actual endpoint may vary
        data = self._get("/vX/reference/financials", params=params)
        return data.get('results', [])

    def get_options_chain(
        self,
        ticker: str,
        expiration_date: str = None,
        contract_type: str = None,
        limit: int = 250
    ) -> list:
        """
        Get options contracts for a ticker.

        Args:
            ticker: Underlying ticker
            expiration_date: Filter by expiry (YYYY-MM-DD)
            contract_type: 'call' or 'put'
            limit: Max results
        """
        params = {'underlying_ticker': ticker, 'limit': limit}
        if expiration_date:
            params['expiration_date'] = expiration_date
        if contract_type:
            params['contract_type'] = contract_type

        data = self._get("/v3/reference/options/contracts", params=params)
        return data.get('results', [])

    def get_option_snapshot(self, ticker: str) -> dict:
        """Get snapshot for all options on underlying ticker."""
        data = self._get(f"/v3/snapshot/options/{ticker}")
        return data.get('results', {})

    def get_market_status(self) -> dict:
        """Get current market status (open/closed)."""
        return self._get("/v1/marketstatus/now")

    def get_gainers_losers(self, direction: str = "gainers") -> list:
        """
        Get top gainers or losers.

        Args:
            direction: 'gainers' or 'losers'
        """
        data = self._get(f"/v2/snapshot/locale/us/markets/stocks/{direction}")
        return data.get('tickers', [])

    def search_tickers(self, query: str, limit: int = 20) -> list:
        """Search for tickers by name or symbol."""
        data = self._get(
            "/v3/reference/tickers",
            params={'search': query, 'active': 'true', 'limit': limit}
        )
        return data.get('results', [])

    # Convenience methods for scanners

    def get_price_data_for_scanner(self, ticker: str, days: int = 60) -> dict:
        """
        Get comprehensive price data for scanner analysis.

        Returns dict with: bars, snapshot, previous_close
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        return {
            'bars': self.get_daily_bars(ticker, start_date, end_date),
            'snapshot': self.get_snapshot(ticker),
            'previous_close': self.get_previous_close(ticker)
        }

    def get_premarket_movers(self) -> dict:
        """Get pre-market gainers and losers."""
        return {
            'gainers': self.get_gainers_losers('gainers'),
            'losers': self.get_gainers_losers('losers')
        }

    def is_market_open(self) -> bool:
        """Check if the stock market is currently open."""
        status = self.get_market_status()
        return status.get('market') == 'open'
