from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Prompt:
    """统一 prompt 结构：便于未来做模板版本化与可观测性。"""

    system: str
    user: str
    meta: Dict[str, Any]


class PromptBuilder:
    """Prompt 构造器：占位实现，后续可接入模板系统。"""

    def build(self, *, template_id: str, variables: Dict[str, Any]) -> Prompt:
        system = str(variables.get("system") or "")
        user = str(variables.get("user") or "")
        return Prompt(system=system, user=user, meta={"template_id": template_id, "variables": dict(variables)})

