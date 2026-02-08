"""
BigDXtremeTrade Dashboard API

FastAPI backend serving scan results.
"""

import os
import sys
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import schedule

# Add project root to sys.path so `src.*` and `config.*` imports resolve
# In local dev, main.py is at web/api/ so root is ../../
# In Azure deploy (flattened), main.py is at root alongside src/ and config/
_script_dir = Path(__file__).parent
if (_script_dir / "src").is_dir():
    PROJECT_ROOT = _script_dir  # flattened deploy
else:
    PROJECT_ROOT = _script_dir.parent.parent  # local dev (web/api -> root)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from scanner_service import ScannerService
from advanced_scanner_service import AdvancedScannerService

# Load .env from project root
load_dotenv(PROJECT_ROOT / ".env")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("BigDXtremeTrade-API")

# Paths
BASE_DIR = PROJECT_ROOT
MAINLIST_PATH = BASE_DIR / "mainlist.csv"
DATA_DIR = BASE_DIR / "data" if (BASE_DIR / "src").is_dir() else BASE_DIR / "web" / "data"
SCAN_RESULTS_FILE = DATA_DIR / "scan_results.json"

# Create data directory
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Global scanner instances
scanner: Optional[ScannerService] = None
advanced_scanner: Optional[AdvancedScannerService] = None

# ── Concurrency guards ───────────────────────────────────────────────────────
_scan_lock = threading.Lock()
_market_scan_running = False
_advanced_scan_running = False

_scan_status = {
    "market": {"last_started": None, "last_completed": None, "last_error": None},
    "advanced": {"last_started": None, "last_completed": None, "last_error": None},
}

ET = ZoneInfo("America/New_York")


def _is_market_hours() -> bool:
    """Return True if current ET time is within market hours (Mon-Fri 9:30-16:00)."""
    now = datetime.now(ET)
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def _run_market_scan_guarded():
    """Run market scan with concurrency guard. Skips if already running."""
    global _market_scan_running
    with _scan_lock:
        if _market_scan_running:
            logger.info("Market scan already running, skipping")
            return
        _market_scan_running = True
    _scan_status["market"]["last_started"] = datetime.now(ET).isoformat()
    try:
        svc = get_scanner()
        results = svc.run_all_scans(fetch_news=True)
        save_results(results)
        _scan_status["market"]["last_completed"] = datetime.now(ET).isoformat()
        _scan_status["market"]["last_error"] = None
        logger.info("Market scan completed and saved")
    except Exception as e:
        _scan_status["market"]["last_error"] = str(e)
        logger.error(f"Market scan failed: {e}")
    finally:
        with _scan_lock:
            _market_scan_running = False


def _run_advanced_scan_guarded():
    """Run advanced scan with concurrency guard. Skips if already running."""
    global _advanced_scan_running
    with _scan_lock:
        if _advanced_scan_running:
            logger.info("Advanced scan already running, skipping")
            return
        _advanced_scan_running = True
    _scan_status["advanced"]["last_started"] = datetime.now(ET).isoformat()
    try:
        svc = get_advanced_scanner()
        results = svc.run_all_advanced()
        save_advanced_results(results)
        _scan_status["advanced"]["last_completed"] = datetime.now(ET).isoformat()
        _scan_status["advanced"]["last_error"] = None
        logger.info("Advanced scan completed and saved")
    except Exception as e:
        _scan_status["advanced"]["last_error"] = str(e)
        logger.error(f"Advanced scan failed: {e}")
    finally:
        with _scan_lock:
            _advanced_scan_running = False


# ── Scheduled jobs ────────────────────────────────────────────────────────────
_advanced_scan_last_date: Optional[str] = None


def _scheduled_market_scan():
    """Triggered every 5 min by scheduler — only fires during market hours."""
    if not _is_market_hours():
        return
    logger.info("Scheduled market scan triggered")
    _run_market_scan_guarded()


def _scheduled_advanced_scan():
    """Triggered every minute by scheduler — fires once per day at 8:00 PM ET."""
    global _advanced_scan_last_date
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return
    if now.hour == 20 and now.minute == 0:
        today = now.strftime("%Y-%m-%d")
        if _advanced_scan_last_date == today:
            return
        _advanced_scan_last_date = today
        logger.info("Scheduled advanced scan triggered (8:00 PM ET)")
        _run_advanced_scan_guarded()


def _scheduler_loop():
    """Background thread that runs pending schedule jobs every 30s."""
    while True:
        schedule.run_pending()
        time.sleep(30)


schedule.every(5).minutes.do(_scheduled_market_scan)
schedule.every(1).minutes.do(_scheduled_advanced_scan)


# ── FastAPI app with lifespan ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    scheduler_thread.start()
    logger.info("Scheduler thread started (market scan every 5 min, advanced scan daily 8 PM ET)")
    yield


app = FastAPI(
    title="BigDXtremeTrade Dashboard API",
    description="End-of-day stock scanner dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend
frontend_url = os.environ.get("FRONTEND_URL", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_advanced_scanner() -> AdvancedScannerService:
    """Get or create advanced scanner instance."""
    global advanced_scanner
    if advanced_scanner is None:
        advanced_scanner = AdvancedScannerService()
    return advanced_scanner


def get_scanner() -> ScannerService:
    """Get or create scanner instance."""
    global scanner
    if scanner is None:
        api_key = os.environ.get("POLYGON_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="POLYGON_API_KEY not configured")
        finviz_session = os.environ.get("FINVIZ_SESSION")
        scanner = ScannerService(api_key, str(MAINLIST_PATH), finviz_session=finviz_session)
    return scanner


def load_cached_results() -> dict:
    """Load cached scan results from file."""
    if SCAN_RESULTS_FILE.exists():
        try:
            with open(SCAN_RESULTS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading cached results: {e}")
    return {}


def save_results(results: dict):
    """Save scan results to file."""
    try:
        with open(SCAN_RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Saved results to {SCAN_RESULTS_FILE}")
    except Exception as e:
        logger.error(f"Error saving results: {e}")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "BigDXtremeTrade Dashboard API",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/scans")
async def get_scans():
    """
    Get latest scan results.

    Returns cached results if available, otherwise empty.
    """
    results = load_cached_results()
    if not results:
        return {
            "scan_time": None,
            "total_stocks": 0,
            "results": {
                "day_up_10": [],
                "day_down_10": [],
                "week_up_20": [],
                "week_down_20": [],
                "month_up_30": [],
                "month_down_30": [],
                "high_rvol": [],
                "earnings_movers": [],
                "after_hours_up": [],
                "after_hours_down": [],
            },
            "message": "No scan results available. Run a scan first.",
        }
    return results


@app.post("/api/scans/run")
async def run_scans(background_tasks: BackgroundTasks, key: str = None):
    """
    Trigger a new scan.

    Can be called manually or by scheduler.
    Requires API key for security.
    """
    expected_key = os.environ.get("SCAN_API_KEY", "dev-key")
    if key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    if _market_scan_running:
        return {"status": "already_running", "message": "Market scan is already in progress."}

    background_tasks.add_task(_run_market_scan_guarded)

    return {
        "status": "started",
        "message": "Scan started in background. Check /api/scans for results.",
    }


@app.get("/api/scans/{scan_type}")
async def get_scan_by_type(scan_type: str):
    """Get results for a specific scan type."""
    valid_types = [
        "day_up_10", "day_down_10",
        "week_up_20", "week_down_20",
        "month_up_30", "month_down_30",
        "high_rvol", "earnings_movers",
        "after_hours_up", "after_hours_down",
    ]
    if scan_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scan type. Valid types: {valid_types}"
        )

    results = load_cached_results()
    scan_results = results.get("results", {}).get(scan_type, [])

    return {
        "scan_type": scan_type,
        "scan_time": results.get("scan_time"),
        "count": len(scan_results),
        "stocks": scan_results,
    }


@app.get("/api/stock/{ticker}")
async def get_stock_detail(ticker: str):
    """Get details for a specific stock from all scans."""
    results = load_cached_results()
    all_results = results.get("results", {})

    stock_data = None
    found_in = []

    for scan_type, stocks in all_results.items():
        for stock in stocks:
            if stock.get("ticker", "").upper() == ticker.upper():
                stock_data = stock
                found_in.append(scan_type)

    if not stock_data:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found in scan results")

    return {
        "ticker": ticker.upper(),
        "data": stock_data,
        "found_in_scans": found_in,
    }


@app.get("/api/mainlist")
async def get_mainlist():
    """Get the full mainlist of stocks."""
    try:
        svc = get_scanner()
        return {
            "count": len(svc.stocks),
            "stocks": [
                {
                    "ticker": s.ticker,
                    "company": s.company,
                    "sector": s.sector,
                    "industry": s.industry,
                }
                for s in svc.stocks
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Advanced Scanner Endpoints ────────────────────────────────────────────────

ADVANCED_RESULTS_FILE = DATA_DIR / "advanced_scan_results.json"


def load_cached_advanced_results() -> dict:
    """Load cached advanced scan results from file."""
    if ADVANCED_RESULTS_FILE.exists():
        try:
            with open(ADVANCED_RESULTS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading cached advanced results: {e}")
    return {}


def save_advanced_results(results: dict):
    """Save advanced scan results to file."""
    try:
        with open(ADVANCED_RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Saved advanced results to {ADVANCED_RESULTS_FILE}")
    except Exception as e:
        logger.error(f"Error saving advanced results: {e}")


@app.get("/api/advanced/scans")
async def get_advanced_scans():
    """Get cached advanced scan results."""
    results = load_cached_advanced_results()
    if not results:
        svc = get_advanced_scanner()
        return svc.get_cached_results()
    return results


@app.post("/api/advanced/scans/run")
async def run_advanced_scans(background_tasks: BackgroundTasks, key: str = None):
    """Trigger all advanced scans in background."""
    expected_key = os.environ.get("SCAN_API_KEY", "dev-key")
    if key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    if _advanced_scan_running:
        return {"status": "already_running", "message": "Advanced scan is already in progress."}

    background_tasks.add_task(_run_advanced_scan_guarded)
    return {
        "status": "started",
        "message": "Advanced scan started in background. Check /api/advanced/scans for results.",
    }


@app.get("/api/advanced/earnings")
async def get_advanced_earnings():
    """Get Earnings Reversal (ERR) results."""
    results = load_cached_advanced_results()
    earnings = results.get('earnings_reversal', [])
    return {
        "scan_type": "earnings_reversal",
        "scan_time": results.get("scan_time"),
        "count": len(earnings),
        "opportunities": earnings,
    }


@app.get("/api/advanced/overextended")
async def get_advanced_overextended():
    """Get Overextension Mean Reversion (OMR) results."""
    results = load_cached_advanced_results()
    overextended = results.get('overextension', [])
    return {
        "scan_type": "overextension",
        "scan_time": results.get("scan_time"),
        "count": len(overextended),
        "opportunities": overextended,
    }


@app.get("/api/advanced/events")
async def get_advanced_events():
    """Get Event Day Volatility results."""
    results = load_cached_advanced_results()
    events = results.get('event_day', [])
    return {
        "scan_type": "event_day",
        "scan_time": results.get("scan_time"),
        "count": len(events),
        "opportunities": events,
    }


@app.get("/api/advanced/orb")
async def get_advanced_orb():
    """Get Opening Range Breakout (ORB) results."""
    results = load_cached_advanced_results()
    orb = results.get('orb', [])
    return {
        "scan_type": "orb",
        "scan_time": results.get("scan_time"),
        "count": len(orb),
        "opportunities": orb,
    }


@app.get("/api/advanced/top")
async def get_top_opportunities(limit: int = 20):
    """Get top opportunities ranked by score."""
    results = load_cached_advanced_results()
    top = results.get('top_opportunities', [])
    return {
        "scan_time": results.get("scan_time"),
        "count": len(top[:limit]),
        "opportunities": top[:limit],
    }


@app.get("/api/scan-status")
async def get_scan_status():
    """Return current scan running state, timestamps, and schedule info."""
    return {
        "market_scan": {
            "running": _market_scan_running,
            "last_started": _scan_status["market"]["last_started"],
            "last_completed": _scan_status["market"]["last_completed"],
            "last_error": _scan_status["market"]["last_error"],
            "schedule": "Every 5 minutes during market hours (9:30 AM - 4:00 PM ET, weekdays)",
        },
        "advanced_scan": {
            "running": _advanced_scan_running,
            "last_started": _scan_status["advanced"]["last_started"],
            "last_completed": _scan_status["advanced"]["last_completed"],
            "last_error": _scan_status["advanced"]["last_error"],
            "schedule": "Daily at 8:00 PM ET (weekdays)",
        },
        "market_hours": _is_market_hours(),
        "current_time_et": datetime.now(ET).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
