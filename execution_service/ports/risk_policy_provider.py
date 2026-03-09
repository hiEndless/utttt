from __future__ import annotations

from typing import Any, Dict, Protocol


class RiskPolicyProvider(Protocol):
    """风控策略端口：提供执行层硬规则。"""

    async def get_risk_policy(self, exchange: str, symbol: str) -> Dict[str, Any]:
        ...

