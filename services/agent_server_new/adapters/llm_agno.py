from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Callable, Dict, List

from agno.agent import Agent
from agno.models.openai import OpenAIChat

from services.agent_server_new.runtime.llm_runtime import LLMRuntimeConfig

logger = logging.getLogger(__name__)


class AgnoLLMObserver:
    """Agno-based observer that returns OpenAI-compatible raw_content payload for decision parsing."""

    def __init__(
        self,
        *,
        model_id: str,
        api_key: str,
        base_url: str = "",
        timeout_s: float = 8.0,
        retry_max: int = 1,
        retry_backoff_s: float = 0.2,
        temperature: float = 0.1,
        agent_factory: Callable[..., Agent] | None = None,
    ) -> None:
        self._model_id = str(model_id or "").strip()
        self._api_key = str(api_key or "").strip()
        self._base_url = str(base_url or "").strip()
        self._timeout_s = max(0.5, float(timeout_s))
        self._retry_max = max(0, int(retry_max))
        self._retry_backoff_s = max(0.0, float(retry_backoff_s))
        self._temperature = float(temperature)
        self._agent_factory = agent_factory or self._build_agent

    @classmethod
    def from_env(cls, *, config: LLMRuntimeConfig) -> "AgnoLLMObserver":
        timeout_raw = str(os.getenv("AGENT_LLM_TIMEOUT_S", "8") or "8").strip()
        retry_max_raw = str(os.getenv("AGENT_LLM_RETRY_MAX", "1") or "1").strip()
        retry_backoff_raw = str(os.getenv("AGENT_LLM_RETRY_BACKOFF_S", "0.2") or "0.2").strip()
        temp_raw = str(os.getenv("AGENT_LLM_TEMPERATURE", "0.1") or "0.1").strip()
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
        try:
            temperature = float(temp_raw)
        except Exception:
            temperature = 0.1
        return cls(
            model_id=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url,
            timeout_s=timeout_s,
            retry_max=retry_max,
            retry_backoff_s=retry_backoff_s,
            temperature=temperature,
        )

    def _resolve_model_id(self, *, prompt_cfg: Dict[str, Any]) -> str:
        candidate = str(prompt_cfg.get("model_id") or "").strip()
        return candidate or self._model_id

    def _build_agent(self, *, model_id: str, focus: str, checklist: List[str], avoid: List[str]) -> Agent:
        model = OpenAIChat(
            id=model_id,
            api_key=self._api_key,
            base_url=self._base_url or None,
            timeout=self._timeout_s,
            max_retries=self._retry_max,
            temperature=self._temperature,
        )
        return Agent(
            model=model,
            markdown=False,
            parse_response=False,
            instructions=[
                "You are a market signal validator.",
                "Return JSON object only.",
                f"focus={focus}",
                f"checklist={','.join(checklist) if checklist else 'none'}",
                f"avoid={','.join(avoid) if avoid else 'none'}",
            ],
        )

    @staticmethod
    def _stringify_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, (dict, list)):
            return json.dumps(content, ensure_ascii=False)
        return str(content or "")

    @staticmethod
    def _extract_usage(run_out: Any) -> Dict[str, Any]:
        usage: Dict[str, Any] = {}
        metrics = getattr(run_out, "metrics", None)
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(metrics, key, None) if metrics is not None else None
            if isinstance(value, (int, float)):
                usage[key] = int(value)
        return usage

    async def observe(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self._model_id:
            raise RuntimeError("agno llm observer requires model_id")
        if not self._api_key:
            raise RuntimeError("agno llm observer requires api_key")

        user_payload = dict(payload or {})
        prompt_cfg = dict(user_payload.get("decision_prompt") or {})
        model_id = self._resolve_model_id(prompt_cfg=prompt_cfg)
        if not model_id:
            raise RuntimeError("agno llm observer requires model_id")
        focus = str(prompt_cfg.get("focus") or "generic_signal_validation").strip()
        checklist = [str(x).strip() for x in list(prompt_cfg.get("checklist") or []) if str(x).strip()]
        avoid = [str(x).strip() for x in list(prompt_cfg.get("avoid") or []) if str(x).strip()]

        for attempt in range(self._retry_max + 1):
            try:
                agent = self._agent_factory(
                    model_id=model_id,
                    focus=focus,
                    checklist=checklist,
                    avoid=avoid,
                )
                run_out = await asyncio.to_thread(agent.run, str(user_payload))
                raw_content = self._stringify_content(getattr(run_out, "content", ""))
                return {
                    "provider": "agno",
                    "model": model_id,
                    "raw_content": raw_content,
                    "usage": self._extract_usage(run_out),
                    "status": "ok",
                }
            except Exception as exc:
                if attempt >= self._retry_max:
                    raise
                logger.warning(
                    "agno llm observer retry attempt=%s/%s err=%s",
                    attempt + 1,
                    self._retry_max + 1,
                    exc,
                )
                delay_s = float(self._retry_backoff_s) * float(2**attempt)
                if delay_s > 0:
                    await asyncio.sleep(delay_s)
        raise RuntimeError("agno llm observer retry exhausted unexpectedly")
