"""
Serializers for converting CLI Opportunity objects to JSON-safe dicts.
"""

from datetime import datetime
from typing import Optional


def serialize_price_level(pl) -> dict:
    """Convert a PriceLevel dataclass to a JSON-safe dict."""
    return {
        'price': round(pl.price, 2),
        'label': pl.label,
        'level_type': pl.level_type,
    }


def serialize_tradeplan(tp) -> Optional[dict]:
    """Convert a Tradeplan dataclass to a JSON-safe dict."""
    if tp is None:
        return None
    return {
        'entry_price': round(tp.entry_price, 2),
        'stop_loss': round(tp.stop_loss, 2),
        'target_1': round(tp.target_1, 2),
        'target_2': round(tp.target_2, 2) if tp.target_2 is not None else None,
        'target_3': round(tp.target_3, 2) if tp.target_3 is not None else None,
        'direction': tp.direction.value if hasattr(tp.direction, 'value') else str(tp.direction),
        'position_size_shares': tp.position_size_shares,
        'option_contract': tp.option_contract,
        'max_risk_dollars': round(tp.max_risk_dollars, 2),
        'risk_per_share': round(tp.risk_per_share, 2),
        'reward_t1': round(tp.reward_t1, 2),
        'risk_reward_t1': round(tp.risk_reward_t1, 2),
    }


def serialize_opportunity(opp) -> dict:
    """Convert an Opportunity dataclass to a JSON-safe dict."""
    return {
        'ticker': opp.ticker,
        'opportunity_type': opp.opportunity_type.value if hasattr(opp.opportunity_type, 'value') else str(opp.opportunity_type),
        'opportunity_type_name': opp.opportunity_type.name if hasattr(opp.opportunity_type, 'name') else str(opp.opportunity_type),
        'direction': opp.direction.value if hasattr(opp.direction, 'value') else str(opp.direction),
        'signal_strength': opp.signal_strength.name if hasattr(opp.signal_strength, 'name') else str(opp.signal_strength),
        'signal_strength_value': opp.signal_strength.value if hasattr(opp.signal_strength, 'value') else 0,
        'detected_at': opp.detected_at.isoformat() if isinstance(opp.detected_at, datetime) else str(opp.detected_at),
        'headline': opp.headline,
        'details': _serialize_details(opp.details),
        'tradeplan': serialize_tradeplan(opp.tradeplan),
        'key_levels': [serialize_price_level(kl) for kl in (opp.key_levels or [])],
        'score': round(opp.score, 1),
        'is_actionable': opp.is_actionable,
    }


def _serialize_details(details: dict) -> dict:
    """Recursively convert detail values to JSON-safe types."""
    if not details:
        return {}
    safe = {}
    for k, v in details.items():
        if isinstance(v, datetime):
            safe[k] = v.isoformat()
        elif hasattr(v, 'value'):  # Enum
            safe[k] = v.value
        elif isinstance(v, float):
            safe[k] = round(v, 4)
        elif isinstance(v, dict):
            safe[k] = _serialize_details(v)
        else:
            safe[k] = v
    return safe
