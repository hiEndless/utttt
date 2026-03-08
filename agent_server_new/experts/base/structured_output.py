from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class StructuredOutput:
    """结构化输出容器：统一承载原始输出与解析结果。"""

    raw: Any
    parsed: Any
    valid: bool
    errors: Optional[Dict[str, Any]] = None


def parse_with_validator(raw: Any, *, validator: Callable[[Any], T]) -> StructuredOutput:
    """占位：未来可替换为 pydantic/jsonschema，并加入重试策略。"""

    try:
        parsed = validator(raw)
        return StructuredOutput(raw=raw, parsed=parsed, valid=True, errors=None)
    except Exception as e:
        return StructuredOutput(raw=raw, parsed=None, valid=False, errors={"error": str(e)})

