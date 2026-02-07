"""
Application settings and configuration.
API keys should be set via environment variables, never hardcoded.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PolygonConfig:
    api_key: str = field(default_factory=lambda: os.environ.get("POLYGON_API_KEY", ""))
    base_url: str = "https://api.polygon.io"
    ws_url: str = "wss://socket.polygon.io"
    max_retries: int = 3
    rate_limit_per_min: int = 5  # Free tier; upgrade for higher


@dataclass
class FinVizConfig:
    """FinViz Elite screener config. Data pulled via screener exports."""
    elite_url: str = "https://elite.finviz.com"
    export_path: str = "data/finviz_exports"


@dataclass
class RiskConfig:
    max_risk_per_trade_pct: float = 0.01       # 1% of account
    max_daily_loss_pct: float = 0.03            # 3% of account
    scale_out_levels: list = field(default_factory=lambda: [0.33, 0.33, 0.34])
    weekly_target_pct: float = 0.05             # 5% weekly target
    reduced_size_after_target: float = 0.50     # Reduce size by 50% after target
    min_risk_reward: float = 2.0                # Minimum 2:1 R/R
    revenge_cooldown_minutes: int = 15


@dataclass
class ScannerThresholds:
    # Earnings Reaction Reversal (ERR)
    err_eps_surprise_min: float = 5.0           # Beat by >5%
    err_revenue_surprise_min: float = 3.0       # Revenue beat >3%
    err_premarket_vol_multiple: float = 2.0     # >2x avg pre-market volume
    err_iv_crush_min: float = 20.0              # IV dropping >20%

    # Overextension Mean-Reversion (OMR)
    omr_atr_multiple_from_ma: float = 5.0       # >5x ATR from 50MA
    omr_consecutive_days_min: int = 5           # >5 consecutive directional days
    omr_rsi_overbought: float = 80.0
    omr_rsi_oversold: float = 20.0

    # Event Day Volatility
    event_iv_rank_min: float = 70.0             # IV Rank >70th percentile
    event_iv_hv_ratio_min: float = 1.5          # IV > 1.5x HV
    event_vix_elevated: float = 18.0

    # Opening Range Breakout (ORB)
    orb_adr_pct_min: float = 5.0               # ADR% >5%
    orb_range_vs_adr_max: float = 0.50         # Opening range <50% of ADR
    orb_volume_breakout_multiple: float = 1.5   # >1.5x avg 5min vol
    orb_rs_rating_min: float = 80.0


@dataclass
class AppConfig:
    polygon: PolygonConfig = field(default_factory=PolygonConfig)
    finviz: FinVizConfig = field(default_factory=FinVizConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    thresholds: ScannerThresholds = field(default_factory=ScannerThresholds)
    account_size: float = float(os.environ.get("ACCOUNT_SIZE", "100000"))
    timezone: str = "US/Eastern"
    log_level: str = "INFO"
    data_dir: str = "data"
    journal_dir: str = "data/journal"


def get_config() -> AppConfig:
    return AppConfig()
