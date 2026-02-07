"""
Risk Manager — enforces position sizing, daily limits, and trade discipline.

"The goal is not to make money. The goal is to not lose money.
The money-making takes care of itself." — SMB Capital
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from src.models.opportunity import Opportunity, Tradeplan, Direction
from config.settings import RiskConfig

logger = logging.getLogger(__name__)


@dataclass
class DailyPnL:
    date: str
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    trades_taken: int = 0
    wins: int = 0
    losses: int = 0
    largest_win: float = 0.0
    largest_loss: float = 0.0

    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses
        return (self.wins / total * 100) if total > 0 else 0.0


class RiskManager:
    """
    Enforces risk rules before any trade is taken.

    Rules:
    1. Max 1% risk per trade
    2. Max 3% daily loss → stop trading
    3. Position sizing based on stop distance
    4. Minimum 2:1 risk/reward
    5. 15-min cooldown after a loss
    6. Reduce size after weekly target hit
    """

    def __init__(self, config: RiskConfig, account_size: float):
        self.config = config
        self.account_size = account_size
        self.daily_pnl = DailyPnL(date=datetime.now().strftime("%Y-%m-%d"))
        self._last_loss_time: datetime | None = None
        self._weekly_pnl: float = 0.0

    @property
    def max_risk_per_trade(self) -> float:
        """Max dollar risk per trade."""
        base = self.account_size * self.config.max_risk_per_trade_pct
        # Reduce if weekly target already hit
        if self._weekly_pnl >= self.account_size * self.config.weekly_target_pct:
            return base * self.config.reduced_size_after_target
        return base

    @property
    def max_daily_loss(self) -> float:
        return self.account_size * self.config.max_daily_loss_pct

    @property
    def is_daily_limit_hit(self) -> bool:
        return self.daily_pnl.realized_pnl <= -self.max_daily_loss

    @property
    def is_in_cooldown(self) -> bool:
        if self._last_loss_time is None:
            return False
        elapsed = (datetime.now() - self._last_loss_time).total_seconds()
        return elapsed < self.config.revenge_cooldown_minutes * 60

    def validate_trade(self, opportunity: Opportunity) -> tuple[bool, str]:
        """
        Validate whether a trade should be taken.
        Returns (approved, reason).
        """
        if self.is_daily_limit_hit:
            return False, f"Daily loss limit hit (${self.daily_pnl.realized_pnl:.0f}). Stop trading."

        if self.is_in_cooldown:
            remaining = self.config.revenge_cooldown_minutes * 60
            if self._last_loss_time:
                remaining -= (datetime.now() - self._last_loss_time).total_seconds()
            return False, f"Cooldown active. Wait {remaining / 60:.0f} more minutes."

        if not opportunity.tradeplan:
            return False, "No trade plan defined."

        plan = opportunity.tradeplan

        if plan.risk_reward_t1 < self.config.min_risk_reward:
            return False, (
                f"R/R too low: {plan.risk_reward_t1:.1f}:1 "
                f"(minimum {self.config.min_risk_reward:.1f}:1)"
            )

        return True, "Trade approved."

    def size_position(self, tradeplan: Tradeplan) -> int:
        """
        Calculate position size in shares based on risk per trade.
        For options, returns number of contracts (1 contract = 100 shares).
        """
        risk_per_share = tradeplan.risk_per_share
        if risk_per_share <= 0:
            return 0

        max_risk = self.max_risk_per_trade
        shares = int(max_risk / risk_per_share)

        # Update the tradeplan
        tradeplan.position_size_shares = shares
        tradeplan.max_risk_dollars = shares * risk_per_share

        return shares

    def size_option_position(self, max_premium_per_contract: float) -> int:
        """
        Size an options position. Risk = total premium paid.
        Returns number of contracts.
        """
        max_risk = self.max_risk_per_trade
        if max_premium_per_contract <= 0:
            return 0
        premium_per_contract = max_premium_per_contract * 100  # 100 shares per contract
        return max(1, int(max_risk / premium_per_contract))

    def record_trade_result(self, pnl: float):
        """Record a trade result and update daily/weekly tracking."""
        self.daily_pnl.realized_pnl += pnl
        self.daily_pnl.trades_taken += 1
        self._weekly_pnl += pnl

        if pnl >= 0:
            self.daily_pnl.wins += 1
            self.daily_pnl.largest_win = max(self.daily_pnl.largest_win, pnl)
        else:
            self.daily_pnl.losses += 1
            self.daily_pnl.largest_loss = min(self.daily_pnl.largest_loss, pnl)
            self._last_loss_time = datetime.now()

        logger.info(
            f"Trade recorded: ${pnl:+.2f} | "
            f"Daily P&L: ${self.daily_pnl.realized_pnl:+.2f} | "
            f"Trades: {self.daily_pnl.trades_taken} | "
            f"Win Rate: {self.daily_pnl.win_rate:.0f}%"
        )

    def get_status(self) -> dict:
        """Get current risk status for dashboard display."""
        return {
            "account_size": self.account_size,
            "max_risk_per_trade": self.max_risk_per_trade,
            "daily_pnl": self.daily_pnl.realized_pnl,
            "daily_limit": self.max_daily_loss,
            "daily_limit_remaining": self.max_daily_loss + self.daily_pnl.realized_pnl,
            "trades_today": self.daily_pnl.trades_taken,
            "win_rate": self.daily_pnl.win_rate,
            "is_daily_limit_hit": self.is_daily_limit_hit,
            "is_in_cooldown": self.is_in_cooldown,
            "weekly_pnl": self._weekly_pnl,
            "weekly_target_hit": self._weekly_pnl >= self.account_size * self.config.weekly_target_pct,
        }
