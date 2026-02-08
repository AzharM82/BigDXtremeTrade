"""
BigDXtremeTrade — Opportunity Scanner CLI

Usage:
    python main.py weekly-prep          # Sunday night preparation
    python main.py premarket            # Pre-market scan (6-9:30 AM ET)
    python main.py orb                  # Opening Range Breakout scan (9:30-10:30 AM)
    python main.py momentum             # Big movers: 10%+ day, 20%+ week
    python main.py scan [TICKER...]     # Scan specific tickers
    python main.py status               # Risk management status
    python main.py report               # Full opportunity report
"""

import sys
import logging
from datetime import datetime

from config.settings import get_config
from src.scanners.opportunity_engine import OpportunityEngine
from src.dashboard.prep_dashboard import PrepDashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("BigDXtremeTrade")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1].lower()

    # Initialize config and engine
    config = get_config()

    # Check for required API key
    if not config.polygon.api_key:
        print("\nError: POLYGON_API_KEY environment variable is not set.")
        print("\nTo set up:")
        print("  1. Copy .env.example to .env")
        print("  2. Add your Polygon.io API key")
        print("  3. Run: set POLYGON_API_KEY=your_key (Windows)")
        print("     Or:  export POLYGON_API_KEY=your_key (Unix)")
        return

    try:
        engine = OpportunityEngine(config)
    except ValueError as e:
        print(f"\nConfiguration error: {e}")
        return

    dashboard = PrepDashboard(config.journal_dir)

    if command == "weekly-prep":
        print("\nRunning weekly preparation scan...\n")
        results = engine.run_weekly_prep()
        output = dashboard.render_weekly_prep(results)
        print(output)

        # Save to journal
        all_opps = results.get("watchlist", [])
        filepath = dashboard.save_journal_entry(all_opps, notes="Weekly prep scan")
        print(f"\nJournal saved: {filepath}")

    elif command == "premarket":
        watchlist = sys.argv[2:] if len(sys.argv) > 2 else None
        print("\nRunning pre-market scan...\n")
        results = engine.run_premarket_scan(watchlist)
        risk_status = engine.risk_mgr.get_status()
        output = dashboard.render_premarket(results, risk_status)
        print(output)

    elif command == "orb":
        watchlist = sys.argv[2:] if len(sys.argv) > 2 else None
        print("\nRunning Opening Range Breakout scan...\n")
        results = engine.run_orb_scan(watchlist)
        orb_opps = results.get("orb_opportunities", [])
        report = engine.format_opportunity_report(orb_opps)
        print(report)

    elif command == "momentum":
        watchlist = sys.argv[2:] if len(sys.argv) > 2 else None
        print("\nRunning Momentum scan (big movers)...\n")
        results = engine.run_momentum_scan(watchlist)

        # Print results by category
        print("=" * 80)
        print(f"  MOMENTUM SCAN — {datetime.now().strftime('%Y-%m-%d %H:%M ET')}")
        print("=" * 80)

        print("\n--- UP 10%+ TODAY " + "─" * 60)
        if results['day_up_10']:
            for opp in results['day_up_10'][:10]:
                print(f"  {opp.ticker:6} | {opp.details.get('change_pct', 0):+.1f}% | "
                      f"RelVol {opp.details.get('relative_volume', 0):.1f}x | "
                      f"Score {opp.score:.0f}")
        else:
            print("  No stocks up 10%+ today")

        print("\n--- DOWN 10%+ TODAY " + "─" * 58)
        if results['day_down_10']:
            for opp in results['day_down_10'][:10]:
                print(f"  {opp.ticker:6} | {opp.details.get('change_pct', 0):+.1f}% | "
                      f"RelVol {opp.details.get('relative_volume', 0):.1f}x | "
                      f"Score {opp.score:.0f}")
        else:
            print("  No stocks down 10%+ today")

        print("\n--- UP 20%+ THIS WEEK " + "─" * 56)
        if results['week_up_20']:
            for opp in results['week_up_20'][:10]:
                print(f"  {opp.ticker:6} | {opp.details.get('week_change_pct', 0):+.1f}% | "
                      f"RSI {opp.details.get('rsi', 0):.0f} | "
                      f"Score {opp.score:.0f}")
        else:
            print("  No stocks up 20%+ this week")

        print("\n--- DOWN 20%+ THIS WEEK " + "─" * 54)
        if results['week_down_20']:
            for opp in results['week_down_20'][:10]:
                print(f"  {opp.ticker:6} | {opp.details.get('week_change_pct', 0):+.1f}% | "
                      f"RSI {opp.details.get('rsi', 0):.0f} | "
                      f"Score {opp.score:.0f}")
        else:
            print("  No stocks down 20%+ this week")

        print("\n" + "=" * 80)

    elif command == "scan":
        tickers = sys.argv[2:]
        if not tickers:
            print("Usage: python main.py scan TICKER1 TICKER2 ...")
            return
        print(f"\nScanning: {', '.join(tickers)}\n")

        # Run all scanners on these tickers
        err_opps = engine.err_scanner.scan(tickers)
        omr_opps = engine.omr_scanner.scan(tickers)
        all_opps = err_opps + omr_opps
        all_opps.sort(key=lambda o: o.score, reverse=True)

        report = engine.format_opportunity_report(all_opps)
        print(report)

    elif command == "status":
        status = engine.risk_mgr.get_status()
        print("\n  RISK MANAGEMENT STATUS")
        print("  " + "=" * 40)
        for key, val in status.items():
            if isinstance(val, float):
                print(f"  {key}: ${val:,.2f}" if "pnl" in key or "risk" in key or "limit" in key or "account" in key
                      else f"  {key}: {val:.1f}")
            else:
                print(f"  {key}: {val}")

    elif command == "report":
        print("\nGenerating full opportunity report...\n")
        engine.run_weekly_prep()
        report = engine.format_opportunity_report()
        print(report)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
