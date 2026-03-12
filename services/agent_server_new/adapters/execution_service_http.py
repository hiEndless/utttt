from __future__ import annotations

import os
from typing import Any, Dict

import httpx

from agent_server_new.ports.execution import ExecutionDecisionProvider


class HttpExecutionDecisionProvider(ExecutionDecisionProvider):
    """通过 HTTP 调用 execution_service 的执行裁决接口。"""

    def __init__(self, base_url: str, *, timeout_s: float = 10.0) -> None:
        self._base_url = str(base_url or "").rstrip("/")
        self._timeout_s = float(timeout_s)

    @classmethod
    def from_env(cls) -> "HttpExecutionDecisionProvider":
        base_url = str(
            os.getenv("AGENT_EXECUTION_BASE_URL", "http://127.0.0.1:9962") or "http://127.0.0.1:9962"
        ).strip()
        timeout_raw = str(os.getenv("AGENT_EXECUTION_TIMEOUT_S", "10") or "10").strip()
        try:
            timeout_s = float(timeout_raw)
        except Exception:
            timeout_s = 10.0
        return cls(base_url=base_url, timeout_s=timeout_s)

    async def decide(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._base_url}/internal/execution/decide"
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        return dict(data or {})
