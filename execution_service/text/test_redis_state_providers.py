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
            "execution:position:binance:ETHUSDT": json.dumps(
                {
                    "position_side": "long",
                    "position_size": 0.3,
                    "max_position_size": 1.2,
                    "cooldown_seconds_left": 5,
                }
            )
        }
    )
    provider = RedisPositionStateProvider(redis_client=client)  # type: ignore[arg-type]
    out = asyncio.run(provider.get_position_state("binance", "ETHUSDT"))
    assert out["position_side"] == "long"
    assert out["position_size"] == 0.3
    assert out["max_position_size"] == 1.2
    assert out["cooldown_seconds_left"] == 5


def test_redis_account_provider_fallback_when_key_missing() -> None:
    client = _FakeRedis({})
    provider = RedisAccountStateProvider(redis_client=client)  # type: ignore[arg-type]
    out = asyncio.run(provider.get_account_state("binance"))
    assert out["exchange"] == "binance"
    assert out["max_drawdown_ratio"] == 0.15
    assert out["current_drawdown_ratio"] == 0.0


def test_redis_risk_policy_provider_parse() -> None:
    client = _FakeRedis(
        {
            "execution:risk_policy:binance:ETHUSDT": json.dumps(
                {"max_position_size": 2.0, "max_drawdown_ratio": 0.08}
            )
        }
    )
    provider = RedisRiskPolicyProvider(redis_client=client)  # type: ignore[arg-type]
    out = asyncio.run(provider.get_risk_policy("binance", "ETHUSDT"))
    assert out["max_position_size"] == 2.0
    assert out["max_drawdown_ratio"] == 0.08
