from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping


@dataclass
class StubPositionStateProvider:
    """最小仓位状态 stub，用于本地联调和测试。"""

    default_state: Dict[str, Any] = field(
        default_factory=lambda: {
            "position_mode": "one_way",
            "position_side": "flat",
            "position_size": 0.0,
            "long_position_size": 0.0,
            "short_position_size": 0.0,
            "max_position_size": 1.0,
            "unrealized_pnl": 0.0,
            "cooldown_seconds_left": 0,
        }
    )
    symbol_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    async def get_position_state(
        self,
        exchange: str,
        symbol: str,
        account_id: str = "main",
    ) -> Dict[str, Any]:
        # 按 symbol 覆盖，便于构造不同仓位场景。
        base = dict(self.default_state)
        override = self.symbol_overrides.get(symbol)
        if override:
            base.update(override)
        base["exchange"] = exchange
        base["symbol"] = symbol
        base["account_id"] = account_id
        return base


@dataclass
class StubAccountStateProvider:
    """最小账户状态 stub，用于本地联调和测试。"""

    default_state: Dict[str, Any] = field(
        default_factory=lambda: {
            "account_equity": 10000.0,
            "available_balance": 8000.0,
            "margin_ratio": 0.2,
            "max_drawdown_ratio": 0.15,
            "current_drawdown_ratio": 0.02,
        }
    )
    exchange_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    async def get_account_state(self, exchange: str, account_id: str = "main") -> Dict[str, Any]:
        state = dict(self.default_state)
        override = self.exchange_overrides.get(exchange)
        if override:
            state.update(override)
        state["exchange"] = exchange
        state["account_id"] = account_id
        return state


def build_stub_state_providers(
    *,
    position_default: Mapping[str, Any] | None = None,
    account_default: Mapping[str, Any] | None = None,
) -> tuple[StubPositionStateProvider, StubAccountStateProvider]:
    """构建默认 stub provider 对，作为 execution 的最小依赖。"""

    position_provider = StubPositionStateProvider(
        default_state=dict(position_default) if position_default is not None else {}
    )
    if not position_provider.default_state:
        position_provider.default_state = StubPositionStateProvider().default_state

    account_provider = StubAccountStateProvider(
        default_state=dict(account_default) if account_default is not None else {}
    )
    if not account_provider.default_state:
        account_provider.default_state = StubAccountStateProvider().default_state
    return position_provider, account_provider
