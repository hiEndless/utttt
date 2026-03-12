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
    """专家执行器：占位实现，后续可接入真实 LLM client 与 guardrail。"""

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
        raw = await call_model(prompt, self._config)
        out = parse_output(raw)
        if out.valid:
            return out
        return out

