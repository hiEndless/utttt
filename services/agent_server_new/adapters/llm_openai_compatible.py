from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict

import httpx

from services.agent_server_new.runtime.llm_runtime import LLMRuntimeConfig

logger = logging.getLogger(__name__)


class OpenAICompatibleLLMObserver:
    """OpenAI-compatible 聊天接口旁路观察器。"""

    def __init__(
        self,
        *,
        model_id: str,
        api_key: str,
        base_url: str = "",
        timeout_s: float = 8.0,
        retry_max: int = 1,
        retry_backoff_s: float = 0.2,
    ) -> None:
        self._model_id = str(model_id or "").strip()
        self._api_key = str(api_key or "").strip()
        self._base_url = str(base_url or "https://api.openai.com/v1").rstrip("/")
        self._timeout_s = max(0.5, float(timeout_s))
        self._retry_max = max(0, int(retry_max))
        self._retry_backoff_s = max(0.0, float(retry_backoff_s))

    def _resolve_model_id(self, *, prompt_cfg: Dict[str, Any]) -> str:
        candidate = str(prompt_cfg.get("model_id") or "").strip()
        return candidate or self._model_id

    @classmethod
    def from_env(cls, *, config: LLMRuntimeConfig) -> "OpenAICompatibleLLMObserver":
        timeout_raw = str(os.getenv("AGENT_LLM_TIMEOUT_S", "8") or "8").strip()
        retry_max_raw = str(os.getenv("AGENT_LLM_RETRY_MAX", "1") or "1").strip()
        retry_backoff_raw = str(os.getenv("AGENT_LLM_RETRY_BACKOFF_S", "0.2") or "0.2").strip()
        try:
            timeout_s = float(timeout_raw)
        except Exception:
            timeout_s = 8.0
        try:
            retry_max = int(retry_max_raw)
        except Exception:
            retry_max = 1
        try:
            retry_backoff_s = float(retry_backoff_raw)
        except Exception:
            retry_backoff_s = 0.2
        return cls(
            model_id=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url,
            timeout_s=timeout_s,
            retry_max=retry_max,
            retry_backoff_s=retry_backoff_s,
        )

    async def observe(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self._model_id:
            raise RuntimeError("llm observer requires model_id")
        if not self._api_key:
            raise RuntimeError("llm observer requires api_key")

        chat_url = f"{self._base_url}/chat/completions"
        user_payload = dict(payload or {})
        prompt_cfg = dict(user_payload.get("decision_prompt") or {})
        model_id = self._resolve_model_id(prompt_cfg=prompt_cfg)
        if not model_id:
            raise RuntimeError("llm observer requires model_id")
        focus = str(prompt_cfg.get("focus") or "generic_signal_validation").strip()
        checklist = [str(x).strip() for x in list(prompt_cfg.get("checklist") or []) if str(x).strip()]
        avoid = [str(x).strip() for x in list(prompt_cfg.get("avoid") or []) if str(x).strip()]
        system_prompt = (
            "You are a market signal validator. "
            "Return concise JSON object only. "
            f"focus={focus}; "
            f"checklist={','.join(checklist) if checklist else 'none'}; "
            f"avoid={','.join(avoid) if avoid else 'none'}."
        )
        body = {
            "model": model_id,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": str(user_payload),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        for attempt in range(self._retry_max + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                    resp = await client.post(chat_url, json=body, headers=headers)
                    resp.raise_for_status()
                    data = dict(resp.json() or {})
                choices = list(data.get("choices") or [])
                first = dict(choices[0] or {}) if choices else {}
                msg = dict(first.get("message") or {})
                return {
                    "provider": "openai_compatible",
                    "model": model_id,
                    "raw_content": str(msg.get("content") or ""),
                    "usage": dict(data.get("usage") or {}),
                    "status": "ok",
                }
            except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
                if attempt >= self._retry_max:
                    raise
                logger.warning(
                    "llm observer retry attempt=%s/%s err=%s",
                    attempt + 1,
                    self._retry_max + 1,
                    exc,
                )
                delay_s = float(self._retry_backoff_s) * float(2**attempt)
                if delay_s > 0:
                    await asyncio.sleep(delay_s)
        raise RuntimeError("llm observer retry exhausted unexpectedly")
