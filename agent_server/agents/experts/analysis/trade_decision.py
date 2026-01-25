from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
# from agent_server.configs.prompts.trade_decision import prompt as default_prompt
from agent_server.configs.prompts.trade_decision_general import prompt as default_prompt
from agent_server.configs.prompts.core_philosophy import CORE_TRADING_PHILOSOPHY
from agno.models.message import Message
import json
import time
from agent_server.agents.utils import (
    _extract_json_from_text,
    _ensure_json_serializable,
    _json_dumps_safe,
)
from agent_server.agent_context.output_store import save_agent_output


def get_prompt_by_theory(theory_type: str = None):
    """根据理论类型获取对应的prompt"""
    if theory_type == "wave":
        from agent_server.configs.prompts.trade_decision_wave import prompt
        return prompt
    elif theory_type == "chan":
        from agent_server.configs.prompts.trade_decision_chan import prompt
        return prompt
    else:
        return default_prompt


class TradeDecisionExpert:
    name = "trade_decision"

    async def run(self, query: str) -> str:

        cfg = get_agent_config(self.name)

        model_id = cfg.get("model_id", "deepseek-ai/DeepSeek-V3")
        base_url = cfg.get("llm_base_url")
        api_key = cfg.get("llm_api_key")
        theory_type = cfg.get("theory_type", None)  # 支持 "wave" 或 "chan"

        # 根据理论类型选择对应的prompt
        base_prompt = get_prompt_by_theory(theory_type)
        
        # 核心逻辑：将核心交易哲学融合到具体的 Prompt 中
        # 这样无论选择哪种理论（Wave/Chan/General），Agent 都会遵循这套经过实战验证的原则
        instructions = f"{CORE_TRADING_PHILOSOPHY}\n\n{base_prompt}"

        model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key)

        agent = Agent(
            model=model,
            instructions=instructions,
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
        event_id = qobj.get("event_id")
        trade_id = qobj.get("trade_id")
        ts = int(time.time() * 1000)

        try:
            payload_obj = final_result if isinstance(final_result, dict) else json.loads(str(final_result))
        except Exception:
            payload_obj = {"raw": final_result}

        try:
            await save_agent_output(self.name, exchange, symbol, ts, payload_obj, event_id=event_id, trade_id=trade_id, model_id=model_id)
        except Exception as e:
            print(f"Failed to save agent output: {e}")

        output = _json_dumps_safe(final_result)
        print(output)
        return output

