"""
Core data models for trading opportunities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OpportunityType(Enum):
    ERR = "earnings_reaction_reversal"
    OMR = "overextension_mean_reversion"
    EVENT = "event_day_volatility"
    SECTOR = "sector_rotation"
    ORB = "opening_range_breakout"


class Direction(Enum):
    LONG = "long"
    SHORT = "short"


class SignalStrength(Enum):
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    EXTREME = 4


@dataclass
class PriceLevel:
    price: float
    label: str
    level_type: str  # "support", "resistance", "ma", "vwap"


@dataclass
class Tradeplan:
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: Optional[float] = None
    target_3: Optional[float] = None
    direction: Direction = Direction.LONG
    position_size_shares: int = 0
    option_contract: Optional[str] = None  # e.g., "GOOG260213C330"
    max_risk_dollars: float = 0.0

    @property
    def risk_per_share(self) -> float:
        return abs(self.entry_price - self.stop_loss)

    @property
    def reward_t1(self) -> float:
        return abs(self.target_1 - self.entry_price)

    @property
    def risk_reward_t1(self) -> float:
        if self.risk_per_share == 0:
            return 0
        return self.reward_t1 / self.risk_per_share


@dataclass
class Opportunity:
    ticker: str
    opportunity_type: OpportunityType
    direction: Direction
    signal_strength: SignalStrength
    detected_at: datetime
    headline: str
    details: dict = field(default_factory=dict)
    tradeplan: Optional[Tradeplan] = None
    key_levels: list[PriceLevel] = field(default_factory=list)
    score: float = 0.0  # 0-100 composite score

    @property
    def is_actionable(self) -> bool:
        return (
            self.signal_strength.value >= SignalStrength.MODERATE.value
            and self.tradeplan is not None
            and self.tradeplan.risk_reward_t1 >= 2.0
        )


@dataclass
class EarningsData:
    ticker: str
    report_date: str
    report_time: str  # "bmo" (before market open) or "amc" (after market close)
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    revenue_estimate: Optional[float] = None
    revenue_actual: Optional[float] = None
    expected_move_pct: Optional[float] = None
    actual_gap_pct: Optional[float] = None

    @property
    def eps_surprise_pct(self) -> Optional[float]:
        if self.eps_estimate and self.eps_actual and self.eps_estimate != 0:
            return ((self.eps_actual - self.eps_estimate) / abs(self.eps_estimate)) * 100
        return None

    @property
    def revenue_surprise_pct(self) -> Optional[float]:
        if self.revenue_estimate and self.revenue_actual and self.revenue_estimate != 0:
            return ((self.revenue_actual - self.revenue_estimate) / abs(self.revenue_estimate)) * 100
        return None

    @property
    def is_beat(self) -> bool:
        eps_beat = self.eps_surprise_pct and self.eps_surprise_pct > 0
        rev_beat = self.revenue_surprise_pct and self.revenue_surprise_pct > 0
        return bool(eps_beat and rev_beat)

    @property
    def gap_contradicts_result(self) -> bool:
        """True if stock gaps opposite to earnings result (the ERR setup)."""
        if self.actual_gap_pct is None:
            return False
        if self.is_beat and self.actual_gap_pct < -1.0:
            return True  # Beat but gapped down
        if not self.is_beat and self.actual_gap_pct > 1.0:
            return True  # Missed but gapped up
        return False


@dataclass
class ExtensionData:
    ticker: str
    current_price: float
    ma_50: float
    atr_14: float
    rsi_14: float
    consecutive_days: int  # positive = up days, negative = down days
    distance_from_52w_high_pct: float
    distance_from_52w_low_pct: float
    relative_volume: float
    avg_dollar_volume: float

    @property
    def atr_multiple_from_ma(self) -> float:
        if self.atr_14 == 0:
            return 0
        return abs(self.current_price - self.ma_50) / self.atr_14

    @property
    def is_overextended_up(self) -> bool:
        return (
            self.current_price > self.ma_50
            and self.atr_multiple_from_ma >= 5.0
            and self.rsi_14 >= 75
        )

    @property
    def is_overextended_down(self) -> bool:
        return (
            self.current_price < self.ma_50
            and self.atr_multiple_from_ma >= 5.0
            and self.rsi_14 <= 25
        )
