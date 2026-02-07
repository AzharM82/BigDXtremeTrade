"""
Opportunity Engine — the main orchestrator.

Runs all scanners, filters, ranks, and presents the best opportunities.
Designed to be called at different times of the trading workflow:
  - Sunday night: weekly preparation
  - Pre-market: morning scan
  - Market hours: real-time ORB and intraday scans
  - Post-market: review and next-day prep
"""

import logging
from datetime import datetime
from typing import Optional

from src.data.polygon_client import PolygonClient
from src.data.finviz_client import FinVizClient
from src.scanners.earnings_reversal import EarningsReversalScanner
from src.scanners.overextension import OverextensionScanner
from src.scanners.event_day import EventDayScanner
from src.scanners.orb_scanner import ORBScanner
from src.utils.risk_manager import RiskManager
from src.models.opportunity import Opportunity, SignalStrength
from config.settings import AppConfig

logger = logging.getLogger(__name__)


class OpportunityEngine:
    """
    Master orchestrator for all opportunity scanners.

    Usage:
        config = get_config()
        engine = OpportunityEngine(config)

        # Sunday night prep
        weekly = engine.run_weekly_prep()

        # Pre-market scan (6-9:30 AM)
        premarket = engine.run_premarket_scan()

        # During market hours (first 30 min)
        orb = engine.run_orb_scan()

        # Get the top opportunities across all scanners
        top = engine.get_top_opportunities(limit=5)
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.polygon = PolygonClient(config.polygon)
        self.finviz = FinVizClient(config.finviz)
        self.risk_mgr = RiskManager(config.risk, config.account_size)

        # Initialize scanners
        self.err_scanner = EarningsReversalScanner(
            self.polygon, self.finviz, config.thresholds
        )
        self.omr_scanner = OverextensionScanner(
            self.polygon, self.finviz, config.thresholds
        )
        self.event_scanner = EventDayScanner(
            self.polygon, config.thresholds
        )
        self.orb_scanner = ORBScanner(
            self.polygon, self.finviz, config.thresholds
        )

        # Store all found opportunities
        self._opportunities: list[Opportunity] = []
        self._last_scan_time: Optional[datetime] = None

    def run_weekly_prep(self) -> dict:
        """
        Sunday night preparation scan.

        Returns dict with:
        - earnings_week: ERR candidates for the week
        - overextended: OMR setups forming
        - events: Macro events this week
        - watchlist: Combined prioritized watchlist
        """
        logger.info("=== WEEKLY PREP SCAN ===")

        results = {
            "scan_time": datetime.now().isoformat(),
            "earnings_week": [],
            "overextended": [],
            "events": [],
            "watchlist": [],
        }

        # 1. Earnings scan for the week
        logger.info("Scanning earnings calendar...")
        err_opps = self.err_scanner.scan()
        results["earnings_week"] = err_opps
        self._opportunities.extend(err_opps)

        # 2. Overextension scan
        logger.info("Scanning for overextended stocks...")
        omr_opps = self.omr_scanner.scan()
        results["overextended"] = omr_opps
        self._opportunities.extend(omr_opps)

        # 3. Event calendar
        logger.info("Checking event calendar...")
        event_opps = self.event_scanner.scan_upcoming(days_ahead=7)
        results["events"] = event_opps
        self._opportunities.extend(event_opps)

        # 4. Build combined watchlist sorted by score
        all_opps = err_opps + omr_opps + event_opps
        all_opps.sort(key=lambda o: o.score, reverse=True)
        results["watchlist"] = all_opps[:20]

        self._last_scan_time = datetime.now()
        logger.info(
            f"Weekly prep complete: {len(err_opps)} ERR, "
            f"{len(omr_opps)} OMR, {len(event_opps)} events"
        )

        return results

    def run_premarket_scan(self, watchlist: list[str] | None = None) -> dict:
        """
        Pre-market scan (6:00-9:30 AM ET).

        Focuses on:
        - Earnings reactions (gap direction vs result)
        - Overnight OMR confirmations (futures reversing)
        - Pre-market volume anomalies
        """
        logger.info("=== PRE-MARKET SCAN ===")

        results = {
            "scan_time": datetime.now().isoformat(),
            "earnings_reactions": [],
            "omr_confirmations": [],
            "all_opportunities": [],
        }

        # Scan earnings reactions
        err_opps = self.err_scanner.scan(watchlist)
        results["earnings_reactions"] = err_opps

        # Check OMR confirmations with pre-market data
        omr_opps = self.omr_scanner.scan(watchlist)
        results["omr_confirmations"] = omr_opps

        all_opps = err_opps + omr_opps
        all_opps.sort(key=lambda o: o.score, reverse=True)
        results["all_opportunities"] = all_opps

        # Validate through risk manager
        for opp in all_opps:
            approved, reason = self.risk_mgr.validate_trade(opp)
            opp.details["risk_approved"] = approved
            opp.details["risk_reason"] = reason
            if approved and opp.tradeplan:
                self.risk_mgr.size_position(opp.tradeplan)

        self._opportunities.extend(all_opps)
        self._last_scan_time = datetime.now()

        return results

    def run_orb_scan(self, watchlist: list[str] | None = None) -> dict:
        """
        Opening Range Breakout scan (9:30-10:30 AM ET).

        Best called after the first 15-30 minutes of trading.
        """
        logger.info("=== ORB SCAN ===")

        orb_opps = self.orb_scanner.scan(watchlist)

        for opp in orb_opps:
            approved, reason = self.risk_mgr.validate_trade(opp)
            opp.details["risk_approved"] = approved
            opp.details["risk_reason"] = reason
            if approved and opp.tradeplan:
                self.risk_mgr.size_position(opp.tradeplan)

        self._opportunities.extend(orb_opps)
        self._last_scan_time = datetime.now()

        return {
            "scan_time": datetime.now().isoformat(),
            "orb_opportunities": orb_opps,
        }

    def get_top_opportunities(self, limit: int = 10,
                              min_strength: SignalStrength = SignalStrength.MODERATE
                              ) -> list[Opportunity]:
        """Get the top N opportunities across all scanners."""
        filtered = [
            o for o in self._opportunities
            if o.signal_strength.value >= min_strength.value
        ]
        filtered.sort(key=lambda o: o.score, reverse=True)
        return filtered[:limit]

    def get_actionable_trades(self) -> list[Opportunity]:
        """Get only risk-approved, actionable trades."""
        return [
            o for o in self._opportunities
            if o.is_actionable and o.details.get("risk_approved", False)
        ]

    def format_opportunity_report(self, opportunities: list[Opportunity] | None = None) -> str:
        """Format opportunities into a readable report."""
        if opportunities is None:
            opportunities = self.get_top_opportunities()

        if not opportunities:
            return "No opportunities found."

        lines = []
        lines.append("=" * 80)
        lines.append(f"  OPPORTUNITY REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M ET')}")
        lines.append("=" * 80)
        lines.append("")

        # Risk status
        status = self.risk_mgr.get_status()
        lines.append(f"  Account: ${status['account_size']:,.0f}")
        lines.append(f"  Daily P&L: ${status['daily_pnl']:+,.0f}")
        lines.append(f"  Risk/Trade: ${status['max_risk_per_trade']:,.0f}")
        lines.append(f"  Daily Limit Remaining: ${status['daily_limit_remaining']:,.0f}")
        if status['is_daily_limit_hit']:
            lines.append("  *** DAILY LIMIT HIT — NO MORE TRADES ***")
        if status['is_in_cooldown']:
            lines.append("  *** COOLDOWN ACTIVE — WAIT ***")
        lines.append("")
        lines.append("-" * 80)

        for i, opp in enumerate(opportunities, 1):
            lines.append("")
            lines.append(f"  #{i} | {opp.headline}")
            lines.append(f"  Score: {opp.score:.0f}/100 | "
                        f"Strength: {opp.signal_strength.name} | "
                        f"Type: {opp.opportunity_type.value}")

            if opp.tradeplan:
                plan = opp.tradeplan
                lines.append(f"  Entry: ${plan.entry_price:.2f} | "
                            f"Stop: ${plan.stop_loss:.2f} | "
                            f"T1: ${plan.target_1:.2f}")
                lines.append(f"  R/R: {plan.risk_reward_t1:.1f}:1 | "
                            f"Size: {plan.position_size_shares} shares | "
                            f"Risk: ${plan.max_risk_dollars:.0f}")

            # Key details
            for key, val in opp.details.items():
                if key not in ("risk_approved", "risk_reason"):
                    lines.append(f"    {key}: {val}")

            approved = opp.details.get("risk_approved")
            if approved is not None:
                status_str = "APPROVED" if approved else f"REJECTED: {opp.details.get('risk_reason', '')}"
                lines.append(f"  Risk Check: {status_str}")

            lines.append("-" * 80)

        return "\n".join(lines)
