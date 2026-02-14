import json
from typing import Dict, Any, List

# =========================
# Expert Registry
# =========================

EXPERT_REGISTRY = {
    "signal_verdict": {
        "role": "Signal Validation Expert",
        "description": "基于多周期结构与风险审计，评估交易信号的有效性与结构自洽性。",
        "interpretation": [
            "audit_breakdown.directional_alignment 中若出现 dominant_cycle 的 CONFLICT，视为主要结构冲突，应严格限制或禁止交易。",
            "audit_confidence.level 为 LOW 或 structural_clarity 为 DOMINANT_CONFLICT / NOISE_DOMINATED 时，意味着信号缺乏结构支持，应采取 defensive 策略。",
            "risk_exposure_flags 若包含高风险标记（如 crowding_risk, liquidity_vacuum），必须在 trade_intent_range 中体现为 risk_bias='defensive' 或 forbidden_actions=['aggressive_add']。",
            "cycle_weights 中 high 权重的周期若出现 CONFLICT，具有否决效应。",
            "leverage_phase_match 为 MISMATCH 时，提示动能可能衰竭，不宜激进追单。"
        ],
        "constraints": [
            "若 dominant_cycle 存在 CONFLICT，禁止 aggressive_add",
            "若 audit_confidence.level = LOW，必须强制 risk_bias 为 conservative 或 defensive",
            "若存在主要结构冲突或高风险标记，禁止 risk_bias = neutral"
        ],
        "priority": 10
    },

    "trade_behavior": {
        "role": "Trade Behavior Audit Expert",
        "description": "提供详细的市场周期行为审计与结构性冲突证据。",
        "interpretation": [
            "dominant_cycle 指示当前市场的主导周期，决策应优先服从主导周期的结构特征。",
            "cycle_weights 描述各周期的结构重要性，high 权重的周期具有否决权。",
            "audit_breakdown.directional_alignment 显示各周期的方向一致性，CONFLICT 暗示逆势风险。",
            "audit_breakdown.leverage_phase_match 显示杠杆周期匹配度，MISMATCH 暗示动能衰竭或反转风险。",
            "risk_exposure_flags 列出了具体的风险点（如 liquidity_vacuum），需在执行中规避。",
            "audit_confidence.structural_clarity 描述结构清晰度。注意：CLEAR_DOMINANT_CYCLE ≠ trend_opportunity（仅表示结构清晰，不代表无风险）；DOMINANT_CONFLICT 或 RISK_CLUSTER_PRESENT 应触发防御性策略。"
        ],
        "constraints": [
            "若 dominant_cycle 处于 CONFLICT 状态，禁止激进追涨杀跌",
            "若存在 high 权重的周期 veto_only 且 directional_alignment 为 CONFLICT，禁止同向开仓",
            "若 audit_confidence 为 LOW 且 structural_clarity 为 NOISE_DOMINATED，应收缩风险暴露"
        ],
        "priority": 15
    },
}

# =========================
# Base Prompt Template
# =========================

_prompt_template = """
你是 **Decision / Trade Intent Agent（交易决策意图生成代理）**。

你的职责是：
- 基于多个专家 Agent 提供的【结构化事实输入】
- 生成一个【交易决策意图范围（trade_intent_range）】
- 不直接生成具体下单参数（价格 / 数量 / 止损）

核心原则（必须遵守）：
1. 不预测价格，不判断市场涨跌
2. 不制造方向性确定性，只定义“允许 / 禁止 / 收缩 / 扩展”的决策空间
3. 当专家意见冲突时，采取保守收敛原则
4. 缺失的专家输入不得被视为隐含利多或利空
5. 【语义映射规则】CLEAR_DOMINANT_CYCLE ≠ trend_opportunity。仅表示“结构主导清晰”，不代表“风险低”。

你将收到若干专家输入，每个专家输入都包含：
- 专家角色说明
- 输入数据的解释规则
- 明确的约束边界

你必须严格遵守这些解释与约束。

==============================
【Expert Inputs】
==============================

{EXPERT_INPUTS}

==============================
【Output Requirements】
==============================

请输出一个 JSON，对当前交易意图进行约束性描述，例如：

{
  "trade_intent_range": {
    "allowed_actions": ["hold", "reduce", "scale_in_small"],
    "forbidden_actions": ["aggressive_add", "reverse_position"],
    "risk_bias": "conservative | neutral | defensive"
  },
  "reasoning": [
    "引用了哪些专家约束",
    "如何处理冲突",
    "为何收敛或放宽决策空间"
  ]
}

==============================
【Risk Bias Semantics（风险偏好语义锚点）】
==============================

- defensive：以风险收敛为主，优先减少或保护已有暴露
- conservative：允许有限执行，但总体偏向谨慎
- neutral：结构与风险未明显约束执行空间

"""


# =========================
# Prompt Builder
# =========================

def _format_list(items: List[str]) -> str:
    if not items:
        return "- None"
    return "\n".join([f"- {item}" for item in items])


def _build_expert_section(key: str, data: Any) -> str:
    spec = EXPERT_REGISTRY[key]

    return f"""
### Expert: {spec['role']}

Description:
{spec['description']}

Interpretation Guidelines:
{_format_list(spec.get("interpretation", []))}

Constraints:
{_format_list(spec.get("constraints", []))}

Input Data:
{json.dumps(data, indent=2, ensure_ascii=False)}
"""


def build_decision_prompt(inputs: Dict[str, Any]) -> str:
    """
    inputs:
        {
            "signal_verdict": {...},
            "market_structure": {...},
            "position_state": {...}
        }
    """

    expert_sections = []

    # 按 priority 排序，保证高约束专家先出现
    for key in sorted(
            inputs.keys(),
            key=lambda k: EXPERT_REGISTRY.get(k, {}).get("priority", 999)
    ):
        if key not in EXPERT_REGISTRY:
            continue

        section = _build_expert_section(key, inputs[key])
        expert_sections.append(section)

    expert_inputs_block = "\n".join(expert_sections)

    final_prompt = _prompt_template.replace(
        "{EXPERT_INPUTS}",
        expert_inputs_block
    )

    return final_prompt


prompt = ""
# =========================
# Example Usage
# =========================

if __name__ == "__main__":
    example_inputs = {
        "meta": {"symbol": "ETHUSDT"},
        "signal_verdict": {
            "dominant_cycle": "mid_term",
            "cycle_weights": {
                "short_term": "low",
                "mid_term": "high",
                "long_term": "veto_only"
            },
            "audit_breakdown": {
                "directional_alignment": {
                    "short_term": "NEUTRAL",
                    "mid_term": "CONFLICT",
                    "long_term": "CONFLICT"
                },
                "leverage_phase_match": {
                    "short_term": "NOT_APPLICABLE",
                    "mid_term": "NOT_APPLICABLE",
                    "long_term": "NOT_APPLICABLE"
                }
            },
            "conflict_evidence": {
                "directional_conflict": ["Mid-term structure shows clear resistance", "Long-term trend is bearish"],
                "leverage_conflict": []
            },
            "risk_exposure_flags": ["crowding_risk"],
            "audit_confidence": {
                "level": "MEDIUM",
                "structural_clarity": "DOMINANT_CONFLICT"
            }
        },
        "trade_behavior_audit": {
            "dominant_cycle": "short_term",
            "cycle_weights": {
                "short_term": "high",
                "mid_term": "medium",
                "long_term": "low"
            },
            "audit_breakdown": {
                "directional_alignment": {
                    "short_term": "ALIGNED",
                    "mid_term": "NEUTRAL",
                    "long_term": "NEUTRAL"
                },
                "leverage_phase_match": {
                    "short_term": "MATCH",
                    "mid_term": "NEUTRAL",
                    "long_term": "NEUTRAL"
                }
            },
            "conflict_evidence": {
                "directional_conflict": [],
                "leverage_conflict": []
            },
            "risk_exposure_flags": [],
            "audit_confidence": {
                "level": "HIGH",
                "structural_clarity": "CLEAR_DOMINANT_CYCLE"
            }
        },
        "market_structure": {"symbol": "ETHUSDT", "pre_decision_structure": {"short_term": {
            "participant_positioning": {"participant_inference": {}, "structural_weight": "low",
                                        "confidence": {"level": "low"}}, "behavioral_intent": {
                "taker_bias": {"dominant_flow": "balanced", "flow_confidence": "medium", "market_mode": "range_flow",
                               "range_stability": "high"}, "confidence": {"level": "medium"}},
            "structural_risks": {"crowding_risk": "high"}}, "mid_term": {"participant_positioning": {
            "participant_inference": {"dominant_group": "mid_term_participants", "behavior": "reducing_leverage",
                                      "positioning_mode": "risk_off", "confidence": {"level": "high"}},
            "structural_weight": "high", "confidence": {"level": "high"}}, "behavioral_intent": {"taker_bias": {},
                                                                                                 "confidence": {
                                                                                                     "level": "low"}},
            "structural_risks": {"crowding_risk": "high"}},
            "long_term": {"structural_context": {
                "trend_maturity": "early",
                "leverage_extreme": False,
                "crowding_percentile": {
                    "zone": "elevated"}},
                "structural_weight": "veto_only",
                "confidence": {
                    "level": "low"}}}},
        "position_state": {'position_side': 'LONG', 'exposure_level': 'small', 'pnl_state': 'small_profit',
                           'holding_bias': 'neutral'}
    }

    prompt = build_decision_prompt(example_inputs)
    print(prompt)
