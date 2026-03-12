from __future__ import annotations

from dataclasses import dataclass
import json
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
    """最小结构化解析器：支持 JSON 字符串输入并返回统一错误结构。"""

    parsed_input = raw
    if isinstance(raw, str):
        raw_str = raw.strip()
        if raw_str.startswith("{") and raw_str.endswith("}"):
            try:
                parsed_input = json.loads(raw_str)
            except Exception:
                parsed_input = raw

    try:
        parsed = validator(parsed_input)
        return StructuredOutput(raw=raw, parsed=parsed, valid=True, errors=None)
    except Exception as e:
        return StructuredOutput(
            raw=raw,
            parsed=None,
            valid=False,
            errors={"error": str(e), "type": e.__class__.__name__},
        )
