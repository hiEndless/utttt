"""
交易决策 Agent - 基于信号验证、风控、市场结构做出开仓/平仓决策
"""

from agno.agent import Agent
from agno.models.openai import OpenAILike
from agno.models.message import Message
from agent_server.configs.source import get_agent_config
from agent_server.configs.prompts.trade_decision_general import get_prompt
from agent_server.configs.prompts.core_philosophy import CORE_TRADING_PHILOSOPHY
import asyncio
import json
import time


def _extract_json_from_text(text: str):
    """从文本中提取 JSON"""
    import re
    if not text or not isinstance(text, str):
        return None
    # 尝试匹配 {...}
    m = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _json_dumps_safe(obj) -> str:
    """安全 JSON 序列化"""
    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(obj)


class TradeDecisionExpert:
    name = "trade_decision"

    def _get_prompt(self) -> str:
        cfg = get_agent_config(self.name)
        theory_type = cfg.get("theory_type")
        if theory_type == "wave":
            try:
                from agent_server.configs.prompts.trade_decision_wave import prompt
                return prompt
            except ImportError:
                pass
        elif theory_type == "chan":
            try:
                from agent_server.configs.prompts.trade_decision_chan import prompt
                return prompt
            except ImportError:
                pass
        lang = cfg.get("language", "zh")
        return get_prompt(lang)

    async def run(self, query: str) -> str:
        cfg = get_agent_config(self.name)
        model_id = cfg.get("model_id", "qwen3-max")
        base_url = cfg.get("llm_base_url")
        api_key = cfg.get("llm_api_key")

        base_prompt = self._get_prompt()
        instructions = f"{CORE_TRADING_PHILOSOPHY}\n\n{base_prompt}"

        model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key)
        agent = Agent(model=model, instructions=instructions)

        msg_content = json.dumps(query, ensure_ascii=False) if isinstance(query, dict) else (query or "{}")
        run_output = None
        for attempt in range(2):
            try:
                run_output = await agent.arun(
                    Message(role="user", content=msg_content),
                    stream=False,
                    debug_mode=True,
                )
                break
            except Exception as e:
                err_str = str(e).lower()
                is_api_glitch = "nonetype" in err_str or "choices" in err_str or "subscriptable" in err_str
                if is_api_glitch and attempt == 0:
                    await asyncio.sleep(2.0)
                    continue
                raise
        if run_output is None:
            return _json_dumps_safe({"decision": "NO_ACTION", "should_execute": False, "error": "LLM 返回为空"})
        content = getattr(run_output, "content", None)
        if content is None or (isinstance(content, str) and not content.strip()):
            return _json_dumps_safe({"decision": "NO_ACTION", "should_execute": False, "error": "LLM content 为空"})
        if isinstance(content, str):
            try:
                final_result = json.loads(content)
            except json.JSONDecodeError:
                extracted = _extract_json_from_text(content)
                final_result = extracted if extracted else {"raw": content}
        elif hasattr(content, "model_dump"):
            final_result = content.model_dump(exclude_none=True)
        else:
            final_result = content if isinstance(content, dict) else {"raw": str(content)}

        if isinstance(final_result, dict) and isinstance(final_result.get("raw"), str):
            extracted_raw = _extract_json_from_text(final_result["raw"])
            if extracted_raw:
                final_result = extracted_raw

        return _json_dumps_safe(final_result)
