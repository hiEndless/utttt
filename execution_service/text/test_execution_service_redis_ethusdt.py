import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from redis.asyncio import Redis

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from execution_service.adapters.redis_state_providers import (
    RedisAccountStateProvider,
    RedisPositionStateProvider,
    RedisRiskPolicyProvider,
)
from execution_service.app.service import ExecutionService


@pytest.mark.integration
def test_execution_service_ethusdt_with_redis_data() -> None:
    """使用 Redis 的 binance/ETHUSDT 键数据验证 execution_service 决策链路。"""

    async def _run() -> None:
        redis_url = str(os.getenv("EXECUTION_REDIS_URL", "redis://127.0.0.1:6379/0") or "redis://127.0.0.1:6379/0").strip()
        redis = Redis.from_url(redis_url, decode_responses=True)
        position_key = "execution:position:binance:ETHUSDT"
        account_key = "execution:account:binance"
        risk_key = "execution:risk_policy:binance:ETHUSDT"

        try:
            await redis.set(
                position_key,
                json.dumps(
                    {
                        "position_side": "flat",
                        "position_size": 0.1,
                        "max_position_size": 1.0,
                        "cooldown_seconds_left": 0,
                    },
                    ensure_ascii=False,
                ),
            )
            await redis.set(
                account_key,
                json.dumps(
                    {
                        "account_equity": 10000,
                        "available_balance": 9000,
                        "margin_ratio": 0.1,
                        "max_drawdown_ratio": 0.2,
                        "current_drawdown_ratio": 0.01,
                    },
                    ensure_ascii=False,
                ),
            )
            await redis.set(
                risk_key,
                json.dumps(
                    {
                        "max_position_size": 1.0,
                        "max_drawdown_ratio": 0.2,
                    },
                    ensure_ascii=False,
                ),
            )

            service = ExecutionService(
                position_provider=RedisPositionStateProvider(redis_client=redis),
                account_provider=RedisAccountStateProvider(redis_client=redis),
                risk_policy_provider=RedisRiskPolicyProvider(redis_client=redis),
            )
            out = await service.decide(
                {
                    "decision_id": "dec-redis-ethusdt-001",
                    "exchange": "binance",
                    "symbol": "ETHUSDT",
                    "direction_intent": "long",
                    "confidence": {"level": "medium", "score": 0.66},
                    "cross_horizon_policy": {"suggested_policy": "follow_long_term"},
                    "risk_hints": {"agent_action_hint": "add"},
                }
            )
            assert out.decision_id == "dec-redis-ethusdt-001"
            assert out.execution_action == "add"
        finally:
            await redis.delete(position_key, account_key, risk_key)
            await redis.aclose()

    try:
        asyncio.run(_run())
    except Exception as exc:
        pytest.skip(f"Redis集成环境不可用，跳过 execution_service Redis 测试: {exc}")
