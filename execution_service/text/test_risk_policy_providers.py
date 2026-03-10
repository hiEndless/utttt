from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
import json

from execution_service.adapters.redis_state_providers import RedisRiskPolicyProvider
from execution_service.adapters.stub_risk_policy_provider import StubRiskPolicyProvider


class _FakeRedis:
    def __init__(self, payloads):
        self._payloads = payloads

    async def get(self, key: str):
        return self._payloads.get(key)


def test_stub_risk_policy_default_fields() -> None:
    provider = StubRiskPolicyProvider()
    out = asyncio.run(provider.get_risk_policy("binance", "ETHUSDT"))
    assert out["max_position_size"] == 1.0
    assert out["max_long_position_size"] == 1.0
    assert out["max_short_position_size"] == 1.0
    assert out["max_drawdown_ratio"] == 0.15
    assert out["position_mode"] == "one_way"
    assert out["allow_dual_side"] is False
    assert out["min_available_balance"] == 0.0
    assert out["max_symbol_exposure_ratio"] == 1.0
    assert out["max_account_notional"] == 1000000000.0
    assert out["max_margin_ratio"] == 1.0
    assert out["max_daily_loss"] == 1000000000.0
    assert out["max_consecutive_loss_count"] == 1000000000
    assert out["simulation_step_size"] == 0.1
    assert out["rule_priority_order"] == [
        "position_limit",
        "cooldown",
        "max_drawdown",
        "account_notional",
        "margin_ratio",
        "daily_loss",
        "consecutive_loss",
        "direction_conflict",
    ]


def test_redis_risk_policy_default_fields_when_key_missing() -> None:
    provider = RedisRiskPolicyProvider(redis_client=_FakeRedis({}))  # type: ignore[arg-type]
    out = asyncio.run(provider.get_risk_policy("binance", "ETHUSDT"))
    assert out["max_position_size"] == 1.0
    assert out["max_long_position_size"] == 1.0
    assert out["max_short_position_size"] == 1.0
    assert out["max_drawdown_ratio"] == 0.15
    assert out["position_mode"] == "one_way"
    assert out["allow_dual_side"] is False
    assert out["min_available_balance"] == 0.0
    assert out["max_symbol_exposure_ratio"] == 1.0
    assert out["max_account_notional"] == 1000000000.0
    assert out["max_margin_ratio"] == 1.0
    assert out["max_daily_loss"] == 1000000000.0
    assert out["max_consecutive_loss_count"] == 1000000000
    assert out["simulation_step_size"] == 0.1
    assert out["rule_priority_order"] == [
        "position_limit",
        "cooldown",
        "max_drawdown",
        "account_notional",
        "margin_ratio",
        "daily_loss",
        "consecutive_loss",
        "direction_conflict",
    ]


def test_redis_risk_policy_parse_extended_fields() -> None:
    redis_payload = {
        "execution:risk_policy:binance:ETHUSDT": json.dumps(
            {
                "max_position_size": 2.0,
                "max_long_position_size": 1.5,
                "max_short_position_size": 1.2,
                "max_drawdown_ratio": 0.08,
                "position_mode": "hedge",
                "allow_dual_side": True,
                "min_available_balance": 120.0,
                "max_symbol_exposure_ratio": 0.35,
                "max_account_notional": 50000.0,
                "max_margin_ratio": 0.5,
                "max_daily_loss": 2000.0,
                "max_consecutive_loss_count": 3,
                "simulation_step_size": 0.2,
                "rule_priority_order": [
                    "max_drawdown",
                    "position_limit",
                    "cooldown",
                    "account_notional",
                    "margin_ratio",
                    "daily_loss",
                    "consecutive_loss",
                    "direction_conflict",
                ],
            }
        )
    }
    provider = RedisRiskPolicyProvider(redis_client=_FakeRedis(redis_payload))  # type: ignore[arg-type]
    out = asyncio.run(provider.get_risk_policy("binance", "ETHUSDT"))
    assert out["max_position_size"] == 2.0
    assert out["max_long_position_size"] == 1.5
    assert out["max_short_position_size"] == 1.2
    assert out["max_drawdown_ratio"] == 0.08
    assert out["position_mode"] == "hedge"
    assert out["allow_dual_side"] is True
    assert out["min_available_balance"] == 120.0
    assert out["max_symbol_exposure_ratio"] == 0.35
    assert out["max_account_notional"] == 50000.0
    assert out["max_margin_ratio"] == 0.5
    assert out["max_daily_loss"] == 2000.0
    assert out["max_consecutive_loss_count"] == 3
    assert out["simulation_step_size"] == 0.2
    assert out["rule_priority_order"] == [
        "max_drawdown",
        "position_limit",
        "cooldown",
        "account_notional",
        "margin_ratio",
        "daily_loss",
        "consecutive_loss",
        "direction_conflict",
    ]
