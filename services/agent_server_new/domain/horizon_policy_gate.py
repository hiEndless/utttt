from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from typing import Any, Dict, List


@dataclass(frozen=True)
class HorizonPolicyGateResult:
    allowed: bool
    reasons: list[str] = field(default_factory=list)


def default_horizon_policy_config() -> Dict[str, Any]:
    return {
        # 仅当 intent=increase 时生效的阻断策略集合
        "block_on_increase_policies": ["wait_confirmation", "reduce_risk"],
    }


def load_horizon_policy_config_from_env() -> Dict[str, Any]:
    """从环境变量加载门控配置。

    支持：
    - AGENT_HORIZON_POLICY_BLOCK_ON_INCREASE=wait_confirmation,reduce_risk
    - AGENT_HORIZON_POLICY_CONFIG_JSON={"block_on_increase_policies":["reduce_risk"]}
    """
    base = default_horizon_policy_config()
    raw_json = str(os.getenv("AGENT_HORIZON_POLICY_CONFIG_JSON", "") or "").strip()
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                base = _normalize_config(parsed)
        except json.JSONDecodeError:
            # JSON 非法时回退默认，不抛异常阻塞流程。
            base = default_horizon_policy_config()

    raw_csv = str(os.getenv("AGENT_HORIZON_POLICY_BLOCK_ON_INCREASE", "") or "").strip()
    if raw_csv:
        items = [x.strip() for x in raw_csv.split(",") if x.strip()]
        base["block_on_increase_policies"] = items
    return _normalize_config(base)


def _normalize_config(config: Dict[str, Any] | None) -> Dict[str, Any]:
    base = default_horizon_policy_config()
    if not isinstance(config, dict):
        return base
    out = dict(base)
    if isinstance(config.get("block_on_increase_policies"), list):
        out["block_on_increase_policies"] = [str(x) for x in list(config.get("block_on_increase_policies") or []) if x]
    return out


def horizon_policy_gate(
    *,
    suggested_policy: str,
    policy_reason: str,
    intent: str,
    config: Dict[str, Any] | None = None,
) -> HorizonPolicyGateResult:
    """跨周期策略门控：在 strategy_gate 前做快速保守决策。"""
    cfg = _normalize_config(config)
    block_set = set([str(x) for x in list(cfg.get("block_on_increase_policies") or []) if x])
    if suggested_policy in block_set and intent == "increase":
        return HorizonPolicyGateResult(allowed=False, reasons=[f"horizon_policy_{suggested_policy}", str(policy_reason or "unknown_reason")])
    return HorizonPolicyGateResult(allowed=True, reasons=[])
