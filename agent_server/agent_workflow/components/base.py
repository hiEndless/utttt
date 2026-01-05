import json
from typing import Any, Dict
from agent_server.utils.redis_client import RedisClient


class BaseWorkflowComponent:
    def _parse_step_content(self, content):
        if isinstance(content, dict):
            return content
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, str):
                    try:
                        parsed = json.loads(parsed)
                    except:
                        pass
                return parsed
            except (json.JSONDecodeError, TypeError):
                try:
                    import ast
                    return ast.literal_eval(content)
                except:
                    pass
        return content

    def _safe_json_dumps(self, data: Any) -> str:
        return json.dumps(data, ensure_ascii=False)

    async def _fetch_market_context(self, exchange: str, symbol: str) -> Dict[str, Any]:
        """
        通用的市场上下文获取方法。
        从 Redis 读取 market_state 并构建标准化的 full_context 结构。
        """
        rc = RedisClient()
        bg_key = f"background:{exchange}:{symbol}:market_state"
        bg_str = await rc.get(bg_key)
        bg = json.loads(bg_str) if bg_str else {}

        full_context = bg if isinstance(bg, dict) and bg else {
            "symbol": symbol, "ts": 0, "market_state": {}, "crowd_state": {}
        }
        return full_context
