from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict

import httpx

from services.agent_server_new.ports.execution import ExecutionDecisionProvider

logger = logging.getLogger(__name__)


class HttpExecutionDecisionProvider(ExecutionDecisionProvider):
    """通过 HTTP 调用 execution_service 的执行裁决接口。"""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 10.0,
        retry_max: int = 0,
        retry_backoff_s: float = 0.2,
        retry_on_statuses: tuple[int, ...] = (429, 500, 502, 503, 504),
    ) -> None:
        self._base_url = str(base_url or "").rstrip("/")
        self._timeout_s = float(timeout_s)
        self._retry_max = max(0, int(retry_max))
        self._retry_backoff_s = max(0.0, float(retry_backoff_s))
        self._retry_on_statuses = tuple(sorted({int(x) for x in tuple(retry_on_statuses or ()) if int(x) > 0}))

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
        retry_max_raw = str(os.getenv("AGENT_EXECUTION_RETRY_MAX", "0") or "0").strip()
        retry_backoff_raw = str(os.getenv("AGENT_EXECUTION_RETRY_BACKOFF_S", "0.2") or "0.2").strip()
        retry_statuses_raw = str(
            os.getenv("AGENT_EXECUTION_RETRY_ON_STATUSES", "429,500,502,503,504") or "429,500,502,503,504"
        ).strip()
        try:
            retry_max = max(0, int(retry_max_raw))
        except Exception:
            retry_max = 0
        try:
            retry_backoff_s = max(0.0, float(retry_backoff_raw))
        except Exception:
            retry_backoff_s = 0.2
        retry_statuses: list[int] = []
        for token in retry_statuses_raw.split(","):
            t = str(token or "").strip()
            if not t:
                continue
            try:
                code = int(t)
            except Exception:
                continue
            if code > 0:
                retry_statuses.append(code)
        if not retry_statuses:
            retry_statuses = [429, 500, 502, 503, 504]
        return cls(
            base_url=base_url,
            timeout_s=timeout_s,
            retry_max=retry_max,
            retry_backoff_s=retry_backoff_s,
            retry_on_statuses=tuple(retry_statuses),
        )

    def _should_retry_http_error(self, exc: httpx.HTTPStatusError) -> bool:
        try:
            status_code = int(exc.response.status_code)
        except Exception:
            status_code = 0
        return status_code in set(self._retry_on_statuses)

    async def decide(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._base_url}/internal/execution/decide"
        for attempt in range(self._retry_max + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                return dict(data or {})
            except httpx.HTTPStatusError as exc:
                if attempt >= self._retry_max or not self._should_retry_http_error(exc):
                    raise
                logger.warning(
                    "execution_decider http status retry attempt=%s/%s status=%s",
                    attempt + 1,
                    self._retry_max + 1,
                    getattr(exc.response, "status_code", "unknown"),
                )
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                if attempt >= self._retry_max:
                    raise
                logger.warning(
                    "execution_decider request retry attempt=%s/%s err=%s",
                    attempt + 1,
                    self._retry_max + 1,
                    exc,
                )
            # Exponential backoff: base * 2^attempt.
            delay_s = float(self._retry_backoff_s) * float(2**attempt)
            if delay_s > 0:
                await asyncio.sleep(delay_s)

        raise RuntimeError("execution_decider retry exhausted unexpectedly")
