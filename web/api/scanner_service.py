"""
Scanner Service - Simplified scans for end-of-day dashboard.

Runs 8 scan types against the mainlist and returns tabular data.
"""

import csv
import logging
import requests
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class StockInfo:
    """Stock info from mainlist.csv"""
    ticker: str
    company: str
    sector: str
    industry: str


@dataclass
class StockScanResult:
    """Result for a single stock in a scan."""
    ticker: str
    company: str
    sector: str
    industry: str
    last_price: float
    change_pct_today: float
    change_pct_5d: float
    change_pct_1m: float
    atr: float
    rvol: float
    after_hours_change_pct: float = 0.0
    news_headline: str = ""
    news_link: str = ""
    news_items: list = field(default_factory=list)
    scan_type: str = ""
    short_ratio: float = 0.0
    float_shares: str = ""
    short_float_pct: float = 0.0


class ScannerService:
    """
    Service that runs all 8 scan types against the mainlist.
    """

    POLYGON_BASE = "https://api.polygon.io"
    FINVIZ_NEWS_URL = "https://finviz.com/quote.ashx"

    def __init__(self, polygon_api_key: str, mainlist_path: str, finviz_session: str = None):
        self.api_key = polygon_api_key
        self.mainlist_path = Path(mainlist_path)
        self.stocks: list[StockInfo] = []
        self._load_mainlist()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if finviz_session:
            self.session.cookies.set('screenerUrl', finviz_session, domain='.finviz.com')

    def _load_mainlist(self):
        """Load stocks from mainlist.csv"""
        self.stocks = []
        with open(self.mainlist_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Ticker'):
                    self.stocks.append(StockInfo(
                        ticker=row['Ticker'].strip(),
                        company=row.get('Company', '').strip(),
                        sector=row.get('Sector', '').strip(),
                        industry=row.get('Industry', '').strip(),
                    ))
        logger.info(f"Loaded {len(self.stocks)} stocks from mainlist")

    def _polygon_get(self, endpoint: str, params: dict = None) -> dict:
        """Make GET request to Polygon API."""
        params = params or {}
        params['apiKey'] = self.api_key
        url = f"{self.POLYGON_BASE}{endpoint}"
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Polygon API error: {e}")
            return {}

    def _get_daily_bars(self, ticker: str, days: int = 60) -> list:
        """Get daily bars for a ticker."""
        end = datetime.now()
        start = end - timedelta(days=days)
        data = self._polygon_get(
            f"/v2/aggs/ticker/{ticker}/range/1/day/{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}",
            params={'adjusted': 'true', 'sort': 'asc', 'limit': 5000}
        )
        return data.get('results', [])

    def _get_snapshot(self, ticker: str) -> dict:
        """Get current snapshot for a ticker."""
        data = self._polygon_get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}")
        return data.get('ticker', {})

    def _get_finviz_data(self, ticker: str) -> dict:
        """Fetch news headline and fundamentals (Short Ratio, Float, Short Float %) from FinViz."""
        result = {
            'news_headline': '',
            'news_link': '',
            'news_items': [],
            'short_ratio': 0.0,
            'float_shares': '',
            'short_float_pct': 0.0,
        }
        try:
            resp = self.session.get(
                self.FINVIZ_NEWS_URL,
                params={'t': ticker},
                timeout=10
            )
            if resp.status_code != 200:
                return result

            html = resp.text

            # Parse news
            news_pattern = r'<a[^>]*class="tab-link-news"[^>]*href="([^"]*)"[^>]*>([^<]+)</a>'
            matches = re.findall(news_pattern, html)
            if matches:
                link, headline = matches[0]
                result['news_headline'] = headline.strip()
                result['news_link'] = link
                # Collect top 3 news articles
                for m_link, m_headline in matches[:3]:
                    result['news_items'].append({
                        'headline': m_headline.strip(),
                        'link': m_link,
                    })

            # Parse fundamentals table for Short Ratio
            sr_match = re.search(r'<td[^>]*class="snapshot-td2-cp"[^>]*>Short Ratio</td>\s*<td[^>]*class="snapshot-td2"[^>]*>([^<]+)</td>', html)
            if sr_match:
                try:
                    result['short_ratio'] = float(sr_match.group(1).strip())
                except (ValueError, TypeError):
                    pass

            # Parse Shs Float
            sf_match = re.search(r'<td[^>]*class="snapshot-td2-cp"[^>]*>Shs Float</td>\s*<td[^>]*class="snapshot-td2"[^>]*>([^<]+)</td>', html)
            if sf_match:
                result['float_shares'] = sf_match.group(1).strip()

            # Parse Short Float / Short Interest
            sfi_match = re.search(r'<td[^>]*class="snapshot-td2-cp"[^>]*>Short (?:Float|Interest)</td>\s*<td[^>]*class="snapshot-td2"[^>]*>([^<]+)</td>', html)
            if sfi_match:
                val = sfi_match.group(1).strip().replace('%', '')
                try:
                    result['short_float_pct'] = float(val)
                except (ValueError, TypeError):
                    pass

            return result
        except Exception as e:
            logger.debug(f"FinViz data error for {ticker}: {e}")
            return result

    def _calc_metrics(self, bars: list) -> dict:
        """Calculate ATR, changes from bars."""
        if len(bars) < 2:
            return {
                'last_price': 0,
                'change_pct_today': 0,
                'change_pct_5d': 0,
                'change_pct_1m': 0,
                'atr': 0,
                'rvol': 0,
            }

        last_price = bars[-1]['c']
        prev_close = bars[-2]['c'] if len(bars) >= 2 else last_price

        # Today's change
        change_today = ((last_price - prev_close) / prev_close * 100) if prev_close else 0

        # 5-day change
        if len(bars) >= 6:
            price_5d_ago = bars[-6]['c']
            change_5d = ((last_price - price_5d_ago) / price_5d_ago * 100) if price_5d_ago else 0
        else:
            change_5d = 0

        # 1-month change (~21 trading days)
        if len(bars) >= 22:
            price_1m_ago = bars[-22]['c']
            change_1m = ((last_price - price_1m_ago) / price_1m_ago * 100) if price_1m_ago else 0
        else:
            change_1m = 0

        # ATR (14-day)
        atr = 0
        if len(bars) >= 15:
            true_ranges = []
            for i in range(1, min(15, len(bars))):
                h = bars[-i]['h']
                l = bars[-i]['l']
                pc = bars[-i-1]['c']
                tr = max(h - l, abs(h - pc), abs(l - pc))
                true_ranges.append(tr)
            atr = sum(true_ranges) / len(true_ranges) if true_ranges else 0

        # Relative Volume (today vs 20-day avg)
        rvol = 1.0
        if len(bars) >= 21:
            today_vol = bars[-1]['v']
            avg_vol = sum(b['v'] for b in bars[-21:-1]) / 20
            rvol = today_vol / avg_vol if avg_vol > 0 else 1.0

        return {
            'last_price': round(last_price, 2),
            'change_pct_today': round(change_today, 2),
            'change_pct_5d': round(change_5d, 2),
            'change_pct_1m': round(change_1m, 2),
            'atr': round(atr, 2),
            'rvol': round(rvol, 2),
        }

    def _build_result(self, stock: StockInfo, bars: list, scan_type: str,
                      news_headline: str = "", news_link: str = "",
                      short_ratio: float = 0.0, float_shares: str = "",
                      short_float_pct: float = 0.0) -> StockScanResult:
        """Build a scan result for a stock."""
        metrics = self._calc_metrics(bars)
        return StockScanResult(
            ticker=stock.ticker,
            company=stock.company,
            sector=stock.sector,
            industry=stock.industry,
            last_price=metrics['last_price'],
            change_pct_today=metrics['change_pct_today'],
            change_pct_5d=metrics['change_pct_5d'],
            change_pct_1m=metrics['change_pct_1m'],
            atr=metrics['atr'],
            rvol=metrics['rvol'],
            news_headline=news_headline,
            news_link=news_link,
            scan_type=scan_type,
            short_ratio=short_ratio,
            float_shares=float_shares,
            short_float_pct=short_float_pct,
        )

    def run_all_scans(self, fetch_news: bool = True) -> dict:
        """
        Run all 8 scans and return results.

        Returns dict with keys for each scan type.
        """
        logger.info(f"Starting scans for {len(self.stocks)} stocks...")

        # Cache bars and metrics for all stocks
        stock_data = {}
        for i, stock in enumerate(self.stocks):
            try:
                bars = self._get_daily_bars(stock.ticker, days=60)
                metrics = self._calc_metrics(bars)
                finviz = {'news_headline': '', 'news_link': '', 'short_ratio': 0.0, 'float_shares': '', 'short_float_pct': 0.0}
                if fetch_news:
                    finviz = self._get_finviz_data(stock.ticker)

                # Fetch snapshot for after-hours / overnight gap data
                snapshot = self._get_snapshot(stock.ticker)
                prev_close = snapshot.get('prevDay', {}).get('c', 0)
                today_open = snapshot.get('day', {}).get('o', 0)
                # Overnight gap = how much the stock moved from yesterday's close to today's open
                ah_change_pct = round(((today_open - prev_close) / prev_close * 100), 2) if prev_close and today_open else 0.0

                stock_data[stock.ticker] = {
                    'stock': stock,
                    'bars': bars,
                    'metrics': metrics,
                    'ah_change_pct': ah_change_pct,
                    'news_headline': finviz['news_headline'],
                    'news_link': finviz['news_link'],
                    'news_items': finviz.get('news_items', []),
                    'short_ratio': finviz['short_ratio'],
                    'float_shares': finviz['float_shares'],
                    'short_float_pct': finviz['short_float_pct'],
                }

                if (i + 1) % 50 == 0:
                    logger.info(f"Processed {i + 1}/{len(self.stocks)} stocks")

            except Exception as e:
                logger.error(f"Error processing {stock.ticker}: {e}")

        # Now categorize into 8 scan types
        results = {
            'day_up_10': [],      # Up 10%+ today
            'day_down_10': [],    # Down 10%+ today
            'week_up_20': [],     # Up 20%+ this week (5 days)
            'week_down_20': [],   # Down 20%+ this week
            'month_up_30': [],    # Up 30%+ this month (bonus scan)
            'month_down_30': [],  # Down 30%+ this month (bonus scan)
            'high_rvol': [],      # RVOL > 2x (unusual volume)
            'earnings_movers': [],  # Stocks with news (proxy for earnings/events)
            'after_hours_up': [],   # Up 1%+ after hours
            'after_hours_down': [], # Down 1%+ after hours
        }

        for ticker, data in stock_data.items():
            stock = data['stock']
            metrics = data['metrics']
            news_headline = data['news_headline']
            news_link = data['news_link']

            ah_change_pct = data.get('ah_change_pct', 0.0)

            result = StockScanResult(
                ticker=stock.ticker,
                company=stock.company,
                sector=stock.sector,
                industry=stock.industry,
                last_price=metrics['last_price'],
                change_pct_today=metrics['change_pct_today'],
                change_pct_5d=metrics['change_pct_5d'],
                change_pct_1m=metrics['change_pct_1m'],
                atr=metrics['atr'],
                rvol=metrics['rvol'],
                after_hours_change_pct=ah_change_pct,
                news_headline=news_headline,
                news_link=news_link,
                news_items=data.get('news_items', []),
                short_ratio=data.get('short_ratio', 0.0),
                float_shares=data.get('float_shares', ''),
                short_float_pct=data.get('short_float_pct', 0.0),
            )

            # Categorize
            if metrics['change_pct_today'] >= 10:
                result.scan_type = 'day_up_10'
                results['day_up_10'].append(asdict(result))

            if metrics['change_pct_today'] <= -10:
                result.scan_type = 'day_down_10'
                results['day_down_10'].append(asdict(result))

            if metrics['change_pct_5d'] >= 20:
                result.scan_type = 'week_up_20'
                results['week_up_20'].append(asdict(result))

            if metrics['change_pct_5d'] <= -20:
                result.scan_type = 'week_down_20'
                results['week_down_20'].append(asdict(result))

            if metrics['change_pct_1m'] >= 30:
                result.scan_type = 'month_up_30'
                results['month_up_30'].append(asdict(result))

            if metrics['change_pct_1m'] <= -30:
                result.scan_type = 'month_down_30'
                results['month_down_30'].append(asdict(result))

            if metrics['rvol'] >= 2.0:
                result.scan_type = 'high_rvol'
                results['high_rvol'].append(asdict(result))

            if news_headline:
                result.scan_type = 'earnings_movers'
                results['earnings_movers'].append(asdict(result))

            if ah_change_pct >= 3.0:
                result.scan_type = 'after_hours_up'
                results['after_hours_up'].append(asdict(result))

            if ah_change_pct <= -3.0:
                result.scan_type = 'after_hours_down'
                results['after_hours_down'].append(asdict(result))

        # Sort each category
        results['day_up_10'].sort(key=lambda x: x['change_pct_today'], reverse=True)
        results['day_down_10'].sort(key=lambda x: x['change_pct_today'])
        results['week_up_20'].sort(key=lambda x: x['change_pct_5d'], reverse=True)
        results['week_down_20'].sort(key=lambda x: x['change_pct_5d'])
        results['month_up_30'].sort(key=lambda x: x['change_pct_1m'], reverse=True)
        results['month_down_30'].sort(key=lambda x: x['change_pct_1m'])
        results['high_rvol'].sort(key=lambda x: x['rvol'], reverse=True)
        results['earnings_movers'].sort(key=lambda x: abs(x['change_pct_today']), reverse=True)
        results['after_hours_up'].sort(key=lambda x: x['after_hours_change_pct'], reverse=True)
        results['after_hours_down'].sort(key=lambda x: x['after_hours_change_pct'])

        logger.info(
            f"Scan complete: "
            f"day_up={len(results['day_up_10'])}, "
            f"day_down={len(results['day_down_10'])}, "
            f"week_up={len(results['week_up_20'])}, "
            f"week_down={len(results['week_down_20'])}, "
            f"month_up={len(results['month_up_30'])}, "
            f"month_down={len(results['month_down_30'])}, "
            f"high_rvol={len(results['high_rvol'])}, "
            f"news={len(results['earnings_movers'])}, "
            f"ah_up={len(results['after_hours_up'])}, "
            f"ah_down={len(results['after_hours_down'])}"
        )

        return {
            'scan_time': datetime.now().isoformat(),
            'total_stocks': len(self.stocks),
            'results': results,
        }
