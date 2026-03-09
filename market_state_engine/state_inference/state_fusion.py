from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from .base import InferenceResult, StateInferencePlugin
from .views import safe_dict


def run_plugins(*, plugins: Iterable[StateInferencePlugin], features: Any) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """按顺序执行插件并融合局部状态。

    设计目标：插件之间仅通过 `context` 传递稳定字段，避免隐式耦合。
    """
    state: Dict[str, Any] = {}
    evidence: Dict[str, Any] = {}
    warnings: List[str] = []

    for plugin in sorted(list(plugins), key=lambda x: int(getattr(x, "order", 1000))):
        plugin_name = str(getattr(plugin, "name", plugin.__class__.__name__))
        try:
            result = plugin.infer(features=features, context=dict(state))
        except Exception as exc:
            warnings.append(f"{plugin_name}: {exc}")
            continue

        if not isinstance(result, InferenceResult):
            warnings.append(f"{plugin_name}: invalid_inference_result")
            continue

        state.update(safe_dict(result.partial_state))
        plugin_evidence = safe_dict(result.evidence)
        if plugin_evidence:
            evidence[plugin_name] = plugin_evidence
        if isinstance(result.warnings, list):
            warnings.extend([str(x) for x in result.warnings if x])

    return state, evidence, sorted(set([str(x) for x in warnings if x]))

