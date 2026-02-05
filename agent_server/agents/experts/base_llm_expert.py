from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, Optional, Union

from agno.agent import Agent
from agno.models.message import Message
from agno.models.openai import OpenAILike

from agent_server.agents.utils import LLMOutputValidator, _json_dumps_safe, validate_with_retry
from agent_server.agent_context.output_store import save_agent_output
from agent_server.configs.source import get_agent_config


QueryInput = Union[str, Dict[str, Any]]


class BaseLLMExpert:
    name: str
    version: str
    SCHEMA: Dict[str, Any]

    def __init__(self, language: str = "zh"):
        self.language = language
        self.validator = LLMOutputValidator(self.SCHEMA)

    def build_instructions(self, target_lang: str, **kwargs: Any) -> str:
        raise NotImplementedError

    def build_llm_input(self, query_obj: Dict[str, Any], **kwargs: Any) -> Any:
        return query_obj

    def postprocess_result(self, result: Dict[str, Any], query_obj: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return result

    def build_fallback_result(self, error: Exception, query_obj: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return {"error": str(error)}

    def normalize_for_storage(self, result: Dict[str, Any], query_obj: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        return result

    def _parse_query(self, query: QueryInput) -> Dict[str, Any]:
        if isinstance(query, dict):
            return query
        if not query:
            return {}
        if isinstance(query, str):
            try:
                return json.loads(query)
            except Exception:
                return {"raw": query}
        return {"raw": query}

    def _build_agent(self, model_id: str, base_url: Optional[str], api_key: Optional[str], instructions: str) -> Agent:
        model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key)
        return Agent(model=model, instructions=instructions)

    async def _run_validated(
        self,
        agent: Agent,
        llm_input: Any,
        on_retry: Optional[Callable[[str], None]],
        max_retries: int,
    ) -> Dict[str, Any]:
        async def _run_llm():
            run_output = await agent.arun(
                Message(role="user", content=json.dumps(llm_input, ensure_ascii=False)),
                stream=False,
                debug_mode=True,
            )
            return run_output.content

        return await validate_with_retry(
            llm_runner=_run_llm,
            validator=self.validator,
            max_retries=max_retries,
            on_retry=on_retry,
        )

    async def run(self, query: QueryInput, **kwargs: Any) -> str:
        cfg = get_agent_config(self.name)
        target_lang = cfg.get("language", self.language)

        model_id = cfg.get("model_id", "deepseek-ai/DeepSeek-V3")
        base_url = cfg.get("llm_base_url")
        api_key = cfg.get("llm_api_key")

        instructions = self.build_instructions(target_lang, **kwargs)
        agent = self._build_agent(model_id=model_id, base_url=base_url, api_key=api_key, instructions=instructions)

        qobj = self._parse_query(query)
        meta = qobj.pop("meta") or {}
        # 将 meta 也传递给 LLM，但仍保持 qobj 作为业务字段集合，便于后续落库与默认值回退
        llm_query_obj = dict(qobj)
        llm_query_obj["meta"] = dict(meta)
        llm_input = self.build_llm_input(llm_query_obj, **kwargs)

        try:
            final_result = await self._run_validated(
                agent=agent,
                llm_input=llm_input,
                on_retry=lambda msg: print(f"[{self.__class__.__name__}] {msg}"),
                max_retries=3,
            )
        except Exception as e:
            print(f"[{self.__class__.__name__}] Validation failed after retries: {e}")
            final_result = self.build_fallback_result(e, qobj, **kwargs)

        try:
            final_result = self.postprocess_result(final_result, qobj, **kwargs)
        except Exception:
            pass

        symbol = qobj.get("symbol") or meta.get("symbol") or "UNKNOWN"
        exchange = qobj.get("exchange") or meta.get("exchange") or "binance"
        event_id = qobj.get("event_id") or meta.get("event_id")
        trade_id = qobj.get("trade_id") or meta.get("trade_id")
        meta["ts"] = int(time.time() * 1000)
        meta["version"] = self.version

        payload_obj: Dict[str, Any]
        try:
            payload_obj = final_result if isinstance(final_result, dict) else json.loads(str(final_result))
        except Exception:
            payload_obj = {"raw": final_result}

        try:
            payload_obj = self.normalize_for_storage(payload_obj, qobj, **kwargs)
        except Exception:
            pass
        payload_obj["meta"] = meta

        try:
            await save_agent_output(
                self.name,
                exchange,
                symbol,
                meta["ts"],
                payload_obj,
                event_id=event_id,
                trade_id=trade_id,
                model_id=model_id,
            )
        except Exception:
            pass

        # 返回给调用方的结果也补充 meta（包含 ts/version），避免下游需要额外查存储
        result_for_return: Dict[str, Any]
        if isinstance(final_result, dict):
            result_for_return = dict(final_result)
        else:
            result_for_return = {"raw": final_result}
        result_for_return["meta"] = meta
        output = _json_dumps_safe(result_for_return)
        print(output)
        return output
