"""
Watchlist configuration for BigDXtremeTrade.

Pre-loaded tickers organized by category. Edit this file to customize your watchlist.
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class WatchlistConfig:
    """Configuration for watchlist categories."""

    # Mega Cap Tech - Always monitor for earnings reactions
    mega_caps: List[str] = field(default_factory=lambda: [
        'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'META', 'NVDA', 'TSLA',
        'BRK.B', 'V', 'JNJ', 'UNH', 'XOM', 'JPM', 'MA', 'PG', 'HD', 'CVX',
        'MRK', 'ABBV', 'LLY', 'PEP', 'KO', 'AVGO', 'COST', 'WMT', 'MCD',
        'CSCO', 'TMO', 'ACN', 'ABT', 'DHR', 'ADBE', 'CRM', 'NKE', 'ORCL'
    ])

    # Financials - Sensitive to rates, earnings reactions
    financials: List[str] = field(default_factory=lambda: [
        'JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'BLK', 'SCHW', 'AXP',
        'USB', 'PNC', 'TFC', 'COF', 'BK', 'STT'
    ])

    # Commodities - Great for overextension trades (Silver, Gold, Oil)
    commodities: List[str] = field(default_factory=lambda: [
        'GLD', 'SLV', 'USO', 'UNG', 'COPX', 'WEAT', 'CORN', 'DBA',
        'GDX', 'GDXJ', 'SIL', 'URA', 'XME', 'FCX', 'NEM', 'GOLD'
    ])

    # Major Indices - Always monitor for ORB and event days
    indices: List[str] = field(default_factory=lambda: [
        'SPY', 'QQQ', 'IWM', 'DIA', 'VTI', 'VTV', 'VUG', 'IJR', 'IJH'
    ])

    # Sector ETFs - Sector rotation plays
    sectors: List[str] = field(default_factory=lambda: [
        'XLK', 'XLF', 'XLV', 'XLY', 'XLC', 'XLI', 'XLP', 'XLE', 'XLU',
        'XLB', 'XLRE'
    ])

    # Leveraged ETFs - High volatility, mean reversion
    leveraged: List[str] = field(default_factory=lambda: [
        'TQQQ', 'SQQQ', 'SPXL', 'SPXS', 'UVXY', 'SVXY', 'TNA', 'TZA',
        'SOXL', 'SOXS', 'LABU', 'LABD', 'FAS', 'FAZ'
    ])

    # Volatility Products - Event day and overextension
    volatility: List[str] = field(default_factory=lambda: [
        'VIX', 'UVXY', 'SVXY', 'VXX', 'VIXY'
    ])

    # High Beta Tech - Volatile movers, ORB candidates
    high_beta_tech: List[str] = field(default_factory=lambda: [
        'NVDA', 'AMD', 'TSLA', 'META', 'NFLX', 'CRM', 'NOW', 'SNOW',
        'PLTR', 'NET', 'CRWD', 'DDOG', 'ZS', 'MDB', 'COIN', 'SHOP',
        'SQ', 'ROKU', 'RBLX', 'U', 'SOFI', 'HOOD', 'AFRM', 'UPST'
    ])

    # Meme / Retail Favorites - High volume, gap plays
    high_retail: List[str] = field(default_factory=lambda: [
        'GME', 'AMC', 'BBBY', 'BB', 'NOK', 'PLTR', 'SOFI', 'RIVN',
        'LCID', 'NIO', 'XPEV', 'LI'
    ])

    # Custom - Your personal picks (add tickers here)
    custom: List[str] = field(default_factory=list)

    def get_all_tickers(self) -> List[str]:
        """Get all unique tickers across all categories."""
        all_tickers = set()
        all_tickers.update(self.mega_caps)
        all_tickers.update(self.financials)
        all_tickers.update(self.commodities)
        all_tickers.update(self.indices)
        all_tickers.update(self.sectors)
        all_tickers.update(self.leveraged)
        all_tickers.update(self.volatility)
        all_tickers.update(self.high_beta_tech)
        all_tickers.update(self.high_retail)
        all_tickers.update(self.custom)
        return sorted(list(all_tickers))

    def get_earnings_watchlist(self) -> List[str]:
        """Get tickers to watch for earnings reactions (mega caps + financials + high beta)."""
        tickers = set()
        tickers.update(self.mega_caps)
        tickers.update(self.financials)
        tickers.update(self.high_beta_tech)
        tickers.update(self.custom)
        return sorted(list(tickers))

    def get_overextension_watchlist(self) -> List[str]:
        """Get tickers to watch for overextension (commodities + leveraged + volatility)."""
        tickers = set()
        tickers.update(self.commodities)
        tickers.update(self.leveraged)
        tickers.update(self.volatility)
        tickers.update(self.indices)
        tickers.update(self.custom)
        return sorted(list(tickers))

    def get_orb_watchlist(self) -> List[str]:
        """Get tickers for Opening Range Breakout (high beta + indices)."""
        tickers = set()
        tickers.update(self.high_beta_tech)
        tickers.update(self.indices)
        tickers.update(self.high_retail)
        tickers.update(self.custom)
        return sorted(list(tickers))

    def get_event_watchlist(self) -> List[str]:
        """Get tickers for event days (indices + volatility + leveraged)."""
        tickers = set()
        tickers.update(self.indices)
        tickers.update(self.volatility)
        tickers.update(self.leveraged)
        return sorted(list(tickers))

    def add_custom(self, tickers: List[str]):
        """Add custom tickers to watchlist."""
        for ticker in tickers:
            if ticker.upper() not in self.custom:
                self.custom.append(ticker.upper())

    def remove_custom(self, tickers: List[str]):
        """Remove custom tickers from watchlist."""
        for ticker in tickers:
            if ticker.upper() in self.custom:
                self.custom.remove(ticker.upper())

    def get_category(self, category: str) -> List[str]:
        """Get tickers for a specific category."""
        categories = {
            'mega_caps': self.mega_caps,
            'financials': self.financials,
            'commodities': self.commodities,
            'indices': self.indices,
            'sectors': self.sectors,
            'leveraged': self.leveraged,
            'volatility': self.volatility,
            'high_beta_tech': self.high_beta_tech,
            'high_retail': self.high_retail,
            'custom': self.custom
        }
        return categories.get(category, [])

    def summary(self) -> Dict[str, int]:
        """Get count summary of watchlist categories."""
        return {
            'mega_caps': len(self.mega_caps),
            'financials': len(self.financials),
            'commodities': len(self.commodities),
            'indices': len(self.indices),
            'sectors': len(self.sectors),
            'leveraged': len(self.leveraged),
            'volatility': len(self.volatility),
            'high_beta_tech': len(self.high_beta_tech),
            'high_retail': len(self.high_retail),
            'custom': len(self.custom),
            'total_unique': len(self.get_all_tickers())
        }


# Default watchlist instance
DEFAULT_WATCHLIST = WatchlistConfig()


# Macro Events Calendar (update weekly)
MACRO_EVENTS = {
    'FOMC': {
        'description': 'Federal Reserve Interest Rate Decision',
        'typical_move': 1.5,  # % expected move in SPY
        'dates': []  # Add dates like '2026-02-15'
    },
    'CPI': {
        'description': 'Consumer Price Index',
        'typical_move': 1.0,
        'dates': []
    },
    'NFP': {
        'description': 'Non-Farm Payrolls (Jobs Report)',
        'typical_move': 0.8,
        'dates': []
    },
    'PPI': {
        'description': 'Producer Price Index',
        'typical_move': 0.6,
        'dates': []
    },
    'GDP': {
        'description': 'Gross Domestic Product',
        'typical_move': 0.5,
        'dates': []
    },
    'PCE': {
        'description': 'Personal Consumption Expenditures',
        'typical_move': 0.8,
        'dates': []
    }
}
