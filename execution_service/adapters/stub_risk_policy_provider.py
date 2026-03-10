from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class StubRiskPolicyProvider:
    """最小风控策略 stub。"""

    default_policy: Dict[str, Any] = field(
        default_factory=lambda: {
            "max_position_size": 1.0,
            "max_long_position_size": 1.0,
            "max_short_position_size": 1.0,
            "max_drawdown_ratio": 0.15,
            "position_mode": "one_way",
            "allow_dual_side": False,
            "min_available_balance": 0.0,
            "max_symbol_exposure_ratio": 1.0,
            "max_account_notional": 1000000000.0,
            "max_margin_ratio": 1.0,
            "simulation_step_size": 0.1,
            "rule_priority_order": [
                "position_limit",
                "cooldown",
                "max_drawdown",
                "account_notional",
                "margin_ratio",
                "direction_conflict",
            ],
        }
    )
    symbol_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    async def get_risk_policy(self, exchange: str, symbol: str) -> Dict[str, Any]:
        policy = dict(self.default_policy)
        override = self.symbol_overrides.get(symbol)
        if override:
            policy.update(override)
        policy["exchange"] = exchange
        policy["symbol"] = symbol
        return policy
