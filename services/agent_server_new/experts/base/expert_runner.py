from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from .prompt_builder import Prompt
from .structured_output import StructuredOutput


@dataclass(frozen=True)
class ExpertRunConfig:
    """专家运行配置：用于统一管理温度/模型路由/重试策略等。"""

    model: str
    temperature: float = 0.2
    max_retries: int = 1


class ExpertRunner:
    """专家执行器：统一处理调用重试与结构化解析。"""

    def __init__(self, *, config: ExpertRunConfig) -> None:
        self._config = config

    async def run(
        self,
        *,
        prompt: Prompt,
        call_model: Callable[[Prompt, ExpertRunConfig], Any],
        parse_output: Callable[[Any], StructuredOutput],
        meta: Optional[Dict[str, Any]] = None,
    ) -> StructuredOutput:
        _ = dict(meta or {})
        attempts = max(1, int(self._config.max_retries) + 1)
        last_out: StructuredOutput | None = None
        for _attempt in range(attempts):
            raw = await call_model(prompt, self._config)
            out = parse_output(raw)
            if out.valid:
                return out
            last_out = out
        return last_out or StructuredOutput(raw=None, parsed=None, valid=False, errors={"error": "empty_result"})
