from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.configs.prompts.kline import get_prompt
from agno.models.message import Message
import json
from agent_server.agents.utils import (
    _extract_json_from_text,
    _json_dumps_safe,
)
from agent_server.agent_context.output_store import save_agent_output


class ForceStatsExpert:
    name = "force_stats"

    async def run(self, query: str) -> str:

        cfg = get_agent_config(self.name)

        model_id = str(cfg.get("model_id") or "").strip()
        base_url = str(cfg.get("llm_base_url") or "").strip() or None
        api_key = str(cfg.get("llm_api_key") or "").strip() or None
        missing_keys: list[str] = []
        if not model_id:
            missing_keys.append("model_id")
        if not base_url:
            missing_keys.append("llm_base_url")
        if not api_key:
            missing_keys.append("llm_api_key")
        if missing_keys:
            return _json_dumps_safe({"error": "agent_config_missing", "missing": missing_keys})

        model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key)

        agent = Agent(
            model=model,
            instructions=get_prompt,
        )

        run_output = await agent.arun(
            Message(role="user", content=json.dumps(query, ensure_ascii=False)),
            stream=False,
            debug_mode=True,
        )
        content = run_output.content
        if isinstance(content, str):
            try:
                final_result = json.loads(content)
            except json.JSONDecodeError:
                extracted = _extract_json_from_text(content)
                if extracted is not None:
                    final_result = extracted
                else:
                    final_result = {"raw": content}
        elif hasattr(content, "model_dump"):
            final_result = content.model_dump(exclude_none=True)
        else:
            final_result = content

        if isinstance(final_result, dict) and isinstance(final_result.get("raw"), str):
            extracted_raw = _extract_json_from_text(final_result["raw"])
            if extracted_raw is not None:
                final_result = extracted_raw

        # 构建产出物系统数据结构
        try:
            qobj = json.loads(query) if isinstance(query, str) else (query or {})
        except Exception:
            qobj = {}
        symbol = qobj.get("symbol") or "UNKNOWN"
        exchange = qobj.get("exchange") or "binance"
        try:
            ts = int(qobj.get("ts") or qobj.get("ts_now") or 0)
        except Exception:
            ts = 0
        try:
            payload_obj = final_result if isinstance(final_result, dict) else json.loads(str(final_result))
        except Exception:
            payload_obj = {"raw": final_result}
        try:
            await save_agent_output(self.name, exchange, symbol, ts, payload_obj)
        except Exception:
            pass

        output = _json_dumps_safe(final_result)
        print(output)
        return output


if __name__ == "__main__":
    expert = ForceStatsExpert()
