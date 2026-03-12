from __future__ import annotations

from typing import Any, Dict, Protocol


class LLMObserver(Protocol):
    """LLM 旁路观察端口：不参与主决策，仅输出辅助分析。"""

    async def observe(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """输入上下文，返回结构化观察结果。"""

