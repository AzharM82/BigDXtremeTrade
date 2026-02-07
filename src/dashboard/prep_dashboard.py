"""
Preparation Dashboard — the command center for daily/weekly planning.

Displays opportunities, trade plans, and risk status in a clear format.
Can output to terminal or generate HTML reports.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.opportunity import Opportunity, OpportunityType

logger = logging.getLogger(__name__)


class PrepDashboard:
    """
    Dashboard for trade preparation and review.

    Modes:
    - weekly_prep: Sunday night overview
    - premarket: Morning game plan
    - intraday: Live opportunity tracking
    - postmarket: End-of-day review
    """

    def __init__(self, journal_dir: str = "data/journal"):
        self.journal_path = Path(journal_dir)
        self.journal_path.mkdir(parents=True, exist_ok=True)

    def render_weekly_prep(self, scan_results: dict) -> str:
        """Render the Sunday night prep dashboard."""
        lines = []
        lines.append(self._header("WEEKLY PREPARATION"))

        # Earnings this week
        earnings = scan_results.get("earnings_week", [])
        lines.append(self._section("EARNINGS WATCH (ERR Candidates)"))
        if earnings:
            for opp in earnings[:10]:
                lines.append(self._opportunity_line(opp))
        else:
            lines.append("  No earnings-based setups found this week.")

        # Overextended
        overextended = scan_results.get("overextended", [])
        lines.append(self._section("OVEREXTENSION WATCH (OMR Candidates)"))
        if overextended:
            for opp in overextended[:10]:
                lines.append(self._opportunity_line(opp))
                details = opp.details
                lines.append(
                    f"    ATR Multiple: {details.get('atr_multiple_from_50ma', 'N/A')}x | "
                    f"RSI: {details.get('rsi_14', 'N/A')} | "
                    f"Consec Days: {details.get('consecutive_days', 'N/A')}"
                )
        else:
            lines.append("  No overextension setups found.")

        # Events
        events = scan_results.get("events", [])
        lines.append(self._section("MACRO EVENTS THIS WEEK"))
        if events:
            for opp in events:
                lines.append(
                    f"  {opp.details.get('event_type', '?')} in "
                    f"{opp.details.get('days_until_event', '?')} days — "
                    f"{opp.headline}"
                )
        else:
            lines.append("  No major macro events loaded.")

        # Top watchlist
        watchlist = scan_results.get("watchlist", [])
        lines.append(self._section("TOP WATCHLIST (Ranked by Score)"))
        for i, opp in enumerate(watchlist[:10], 1):
            lines.append(
                f"  {i}. [{opp.opportunity_type.value[:3].upper()}] "
                f"{opp.ticker} — Score: {opp.score:.0f} — "
                f"{opp.signal_strength.name}"
            )

        return "\n".join(lines)

    def render_premarket(self, scan_results: dict, risk_status: dict) -> str:
        """Render the pre-market game plan."""
        lines = []
        lines.append(self._header("PRE-MARKET GAME PLAN"))

        # Risk status
        lines.append(self._section("RISK STATUS"))
        lines.append(f"  Account: ${risk_status['account_size']:,.0f}")
        lines.append(f"  Max Risk/Trade: ${risk_status['max_risk_per_trade']:,.0f}")
        lines.append(f"  Daily Loss Limit: ${risk_status['daily_limit']:,.0f}")
        if risk_status.get("weekly_target_hit"):
            lines.append("  ** WEEKLY TARGET HIT — Reduced size active **")

        # Earnings reactions
        reactions = scan_results.get("earnings_reactions", [])
        lines.append(self._section("EARNINGS REACTIONS"))
        if reactions:
            for opp in reactions:
                lines.append(self._opportunity_line(opp))
                if opp.tradeplan:
                    lines.append(self._tradeplan_line(opp.tradeplan))
        else:
            lines.append("  No ERR setups this morning.")

        # OMR confirmations
        omr = scan_results.get("omr_confirmations", [])
        lines.append(self._section("OVEREXTENSION CONFIRMATIONS"))
        if omr:
            for opp in omr:
                lines.append(self._opportunity_line(opp))
                if opp.tradeplan:
                    lines.append(self._tradeplan_line(opp.tradeplan))
        else:
            lines.append("  No OMR confirmations.")

        # Action items
        all_opps = scan_results.get("all_opportunities", [])
        actionable = [o for o in all_opps if o.details.get("risk_approved")]
        lines.append(self._section(f"ACTIONABLE TRADES ({len(actionable)})"))
        for opp in actionable:
            lines.append(f"  >>> {opp.headline}")
            if opp.tradeplan:
                lines.append(self._tradeplan_line(opp.tradeplan))

        return "\n".join(lines)

    def save_journal_entry(self, opportunities: list[Opportunity],
                           notes: str = "") -> str:
        """Save today's opportunities and notes to journal."""
        today = datetime.now().strftime("%Y-%m-%d")
        entry = {
            "date": today,
            "timestamp": datetime.now().isoformat(),
            "opportunities": [
                {
                    "ticker": o.ticker,
                    "type": o.opportunity_type.value,
                    "direction": o.direction.value,
                    "score": o.score,
                    "headline": o.headline,
                    "details": o.details,
                    "tradeplan": {
                        "entry": o.tradeplan.entry_price,
                        "stop": o.tradeplan.stop_loss,
                        "t1": o.tradeplan.target_1,
                        "rr": o.tradeplan.risk_reward_t1,
                    } if o.tradeplan else None,
                }
                for o in opportunities
            ],
            "notes": notes,
        }

        filepath = self.journal_path / f"{today}.json"
        with open(filepath, "w") as f:
            json.dump(entry, f, indent=2)

        logger.info(f"Journal saved to {filepath}")
        return str(filepath)

    # ── Formatting helpers ───────────────────────────────────────────

    def _header(self, title: str) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M ET")
        return (
            f"\n{'=' * 80}\n"
            f"  {title} — {now}\n"
            f"{'=' * 80}\n"
        )

    def _section(self, title: str) -> str:
        return f"\n--- {title} {'─' * (70 - len(title))}\n"

    def _opportunity_line(self, opp: Opportunity) -> str:
        return (
            f"  [{opp.signal_strength.name:8}] {opp.ticker:6} | "
            f"Score: {opp.score:5.1f} | {opp.headline}"
        )

    def _tradeplan_line(self, plan) -> str:
        return (
            f"    PLAN: Entry ${plan.entry_price:.2f} | "
            f"Stop ${plan.stop_loss:.2f} | "
            f"T1 ${plan.target_1:.2f} | "
            f"R/R {plan.risk_reward_t1:.1f}:1 | "
            f"Size: {plan.position_size_shares} sh"
        )
