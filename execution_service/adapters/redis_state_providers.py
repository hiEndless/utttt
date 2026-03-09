from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from redis.asyncio import Redis


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_json_load(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
        return dict(parsed) if isinstance(parsed, dict) else {}
    except Exception:
        return {}


@dataclass
class RedisExecutionStateConfig:
    """Redis 状态读取配置。"""

    redis_url: str
    decode_responses: bool = True
    position_key_template: str = "execution:position:{exchange}:{account_id}:{symbol}"
    account_key_template: str = "execution:account:{exchange}:{account_id}"
    risk_policy_key_template: str = "execution:risk_policy:{exchange}:{symbol}"

    @classmethod
    def from_env(cls) -> "RedisExecutionStateConfig":
        return cls(
            redis_url=str(os.getenv("EXECUTION_REDIS_URL", "redis://127.0.0.1:6379/0") or "redis://127.0.0.1:6379/0").strip(),
            decode_responses=True,
            position_key_template=str(
                os.getenv("EXECUTION_POSITION_KEY_TEMPLATE", "execution:position:{exchange}:{account_id}:{symbol}")
                or "execution:position:{exchange}:{account_id}:{symbol}"
            ).strip(),
            account_key_template=str(
                os.getenv("EXECUTION_ACCOUNT_KEY_TEMPLATE", "execution:account:{exchange}:{account_id}")
                or "execution:account:{exchange}:{account_id}"
            ).strip(),
            risk_policy_key_template=str(
                os.getenv(
                    "EXECUTION_RISK_POLICY_KEY_TEMPLATE",
                    "execution:risk_policy:{exchange}:{symbol}",
                )
                or "execution:risk_policy:{exchange}:{symbol}"
            ).strip(),
        )


class RedisPositionStateProvider:
    """从 Redis 读取仓位状态。"""

    def __init__(
        self,
        *,
        redis_client: Redis,
        key_template: str = "execution:position:{exchange}:{account_id}:{symbol}",
    ) -> None:
        self._redis = redis_client
        self._key_template = key_template

    async def get_position_state(self, exchange: str, symbol: str, account_id: str = "main") -> Dict[str, Any]:
        key = self._key_template.format(exchange=exchange, account_id=account_id, symbol=symbol)
        raw = await self._redis.get(key)
        payload = _safe_json_load(raw)
        # 中文注释：保证关键字段有默认值，避免裁决器遇到缺失字段崩溃。
        return {
            "exchange": exchange,
            "account_id": account_id,
            "symbol": symbol,
            "position_mode": str(payload.get("position_mode", "one_way") or "one_way").lower(),
            "position_side": str(payload.get("position_side", "flat") or "flat").lower(),
            "position_size": _to_float(payload.get("position_size"), 0.0),
            "long_position_size": _to_float(payload.get("long_position_size"), 0.0),
            "short_position_size": _to_float(payload.get("short_position_size"), 0.0),
            "max_position_size": _to_float(payload.get("max_position_size"), 1.0),
            "unrealized_pnl": _to_float(payload.get("unrealized_pnl"), 0.0),
            "cooldown_seconds_left": _to_int(payload.get("cooldown_seconds_left"), 0),
        }


class RedisAccountStateProvider:
    """从 Redis 读取账户状态。"""

    def __init__(
        self,
        *,
        redis_client: Redis,
        key_template: str = "execution:account:{exchange}:{account_id}",
    ) -> None:
        self._redis = redis_client
        self._key_template = key_template

    async def get_account_state(self, exchange: str, account_id: str = "main") -> Dict[str, Any]:
        key = self._key_template.format(exchange=exchange, account_id=account_id)
        raw = await self._redis.get(key)
        payload = _safe_json_load(raw)
        return {
            "exchange": exchange,
            "account_id": account_id,
            "account_equity": _to_float(payload.get("account_equity"), 0.0),
            "available_balance": _to_float(payload.get("available_balance"), 0.0),
            "margin_ratio": _to_float(payload.get("margin_ratio"), 0.0),
            "max_drawdown_ratio": _to_float(payload.get("max_drawdown_ratio"), 0.15),
            "current_drawdown_ratio": _to_float(payload.get("current_drawdown_ratio"), 0.0),
        }


class RedisRiskPolicyProvider:
    """从 Redis 读取风控策略。"""

    def __init__(
        self,
        *,
        redis_client: Redis,
        key_template: str = "execution:risk_policy:{exchange}:{symbol}",
    ) -> None:
        self._redis = redis_client
        self._key_template = key_template

    async def get_risk_policy(self, exchange: str, symbol: str) -> Dict[str, Any]:
        key = self._key_template.format(exchange=exchange, symbol=symbol)
        raw = await self._redis.get(key)
        payload = _safe_json_load(raw)
        return {
            "exchange": exchange,
            "symbol": symbol,
            "max_position_size": _to_float(payload.get("max_position_size"), 1.0),
            "max_long_position_size": _to_float(payload.get("max_long_position_size"), _to_float(payload.get("max_position_size"), 1.0)),
            "max_short_position_size": _to_float(payload.get("max_short_position_size"), _to_float(payload.get("max_position_size"), 1.0)),
            "max_drawdown_ratio": _to_float(payload.get("max_drawdown_ratio"), 0.15),
            "position_mode": str(payload.get("position_mode", "one_way") or "one_way").lower(),
            "allow_dual_side": bool(payload.get("allow_dual_side", False)),
            "min_available_balance": _to_float(payload.get("min_available_balance"), 0.0),
            "max_symbol_exposure_ratio": _to_float(payload.get("max_symbol_exposure_ratio"), 1.0),
            "simulation_step_size": _to_float(payload.get("simulation_step_size"), 0.1),
        }


def create_redis_client_from_env(redis_url: Optional[str] = None) -> Redis:
    cfg = RedisExecutionStateConfig.from_env()
    return Redis.from_url(redis_url or cfg.redis_url, decode_responses=cfg.decode_responses)
