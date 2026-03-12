from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class Prompt:
    """统一 prompt 结构：便于未来做模板版本化与可观测性。"""

    system: str
    user: str
    meta: Dict[str, Any]


class PromptBuilder:
    """最小模板化 Prompt 构造器，提供变量约束与审计元信息。"""

    def __init__(self, *, templates: Mapping[str, Dict[str, str]] | None = None) -> None:
        self._templates = dict(templates or {})

    def build(self, *, template_id: str, variables: Dict[str, Any]) -> Prompt:
        vars_dict = dict(variables or {})
        tpl = dict(self._templates.get(template_id) or {})

        if tpl:
            required = [str(x).strip() for x in str(tpl.get("required_vars") or "").split(",") if str(x).strip()]
            missing = [k for k in required if k not in vars_dict]
            if missing:
                raise ValueError(f"missing template vars for {template_id}: {','.join(missing)}")
            system_tpl = str(tpl.get("system") or "")
            user_tpl = str(tpl.get("user") or "")
            system = system_tpl.format(**vars_dict)
            user = user_tpl.format(**vars_dict)
        else:
            system = str(vars_dict.get("system") or "")
            user = str(vars_dict.get("user") or "")

        return Prompt(
            system=system,
            user=user,
            meta={
                "template_id": str(template_id),
                "variables": vars_dict,
                "template_registered": bool(tpl),
            },
        )
