from __future__ import annotations

from typing import Any, Dict, Protocol


class AccountStateProvider(Protocol):
    """账户状态端口：提供保证金、可用余额、权益与账户级风险信息。"""

    async def get_account_state(self, exchange: str, account_id: str = "main") -> Dict[str, Any]:
        ...
