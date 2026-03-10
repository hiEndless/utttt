from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
import json

from execution_service.adapters.redis_state_providers import (
    RedisAccountStateProvider,
    RedisPositionStateProvider,
    RedisRiskPolicyProvider,
)


class _FakeRedis:
    def __init__(self, payloads):
        self._payloads = payloads

    async def get(self, key: str):
        return self._payloads.get(key)


def test_redis_position_provider_parse_and_defaults() -> None:
    client = _FakeRedis(
        {
            "execution:position:binance:main:ETHUSDT": json.dumps(
                {
                    "position_mode": "hedge",
                    "position_side": "long",
                    "position_size": 0.3,
                    "long_position_size": 0.3,
                    "short_position_size": 0.1,
                    "max_position_size": 1.2,
                    "cooldown_seconds_left": 5,
                }
            )
        }
    )
    provider = RedisPositionStateProvider(redis_client=client)  # type: ignore[arg-type]
    out = asyncio.run(provider.get_position_state("binance", "ETHUSDT", account_id="main"))
    assert out["position_side"] == "long"
    assert out["position_size"] == 0.3
    assert out["long_position_size"] == 0.3
    assert out["short_position_size"] == 0.1
    assert out["position_mode"] == "hedge"
    assert out["max_position_size"] == 1.2
    assert out["cooldown_seconds_left"] == 5
    assert out["account_id"] == "main"


def test_redis_account_provider_fallback_when_key_missing() -> None:
    client = _FakeRedis({})
    provider = RedisAccountStateProvider(redis_client=client)  # type: ignore[arg-type]
    out = asyncio.run(provider.get_account_state("binance", account_id="main"))
    assert out["exchange"] == "binance"
    assert out["max_drawdown_ratio"] == 0.15
    assert out["current_drawdown_ratio"] == 0.0
    assert out["daily_loss"] == 0.0
    assert out["consecutive_loss_count"] == 0
    assert out["account_id"] == "main"


def test_redis_risk_policy_provider_parse() -> None:
    client = _FakeRedis(
        {
            "execution:risk_policy:binance:ETHUSDT": json.dumps(
                {
                    "max_position_size": 2.0,
                    "max_drawdown_ratio": 0.08,
                    "min_available_balance": 50.0,
                    "max_symbol_exposure_ratio": 0.4,
                    "simulation_step_size": 0.15,
                }
            )
        }
    )
    provider = RedisRiskPolicyProvider(redis_client=client)  # type: ignore[arg-type]
    out = asyncio.run(provider.get_risk_policy("binance", "ETHUSDT"))
    assert out["max_position_size"] == 2.0
    assert out["max_long_position_size"] == 2.0
    assert out["max_short_position_size"] == 2.0
    assert out["max_drawdown_ratio"] == 0.08
    assert out["min_available_balance"] == 50.0
    assert out["max_symbol_exposure_ratio"] == 0.4
    assert out["max_account_notional"] == 1000000000.0
    assert out["max_margin_ratio"] == 1.0
    assert out["max_daily_loss"] == 1000000000.0
    assert out["max_consecutive_loss_count"] == 1000000000
    assert out["simulation_step_size"] == 0.15
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


def test_redis_risk_policy_provider_parse_rule_priority_order_from_csv() -> None:
    client = _FakeRedis(
        {
            "execution:risk_policy:binance:ETHUSDT": json.dumps(
                {
                    "rule_priority_order": "max_drawdown,position_limit,cooldown,account_notional,margin_ratio,daily_loss,consecutive_loss,direction_conflict",
                }
            )
        }
    )
    provider = RedisRiskPolicyProvider(redis_client=client)  # type: ignore[arg-type]
    out = asyncio.run(provider.get_risk_policy("binance", "ETHUSDT"))
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
