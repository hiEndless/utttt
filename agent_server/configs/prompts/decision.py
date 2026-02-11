import json
from typing import Dict, Any, List

# =========================
# Expert Registry
# =========================

EXPERT_REGISTRY = {
    "signal_verdict": {
        "role": "Signal Confirmation Expert",
        "description": "评估交易信号在当前多周期结构与人群状态下的方向一致性与风险有效性。",
        "interpretation": [
            "verdict 是核心执行指令：VALID (正常) / WEAK_VALID (降权) / INVALID (禁止)",
            "WEAK_VALID (原 ATTENUATE) 意味着方向未被否决，但存在中期结构冲突或风险，必须降低执行强度（如减半仓位、收紧止损）。",
            "INVALID (原 BLOCK) 意味着禁止开仓，仅允许持仓管理（Hold/Reduce）。",
            "risk_flags 若包含 crowding_risk 或 liquidity_risk，必须在 trade_intent_range 中体现为 risk_bias='defensive' 或 forbidden_actions=['aggressive_add']。",
            "alignment.breakdown 若显示 short_term=CONFLICT 但 mid_term=ALIGNED，通常暗示回调入场机会（Dip Buy），而非反转。",
            "confidence_adjustment='down' 应直接导致 risk_bias 的保守化。"
        ],
        "constraints": [
            "INVALID 状态下禁止任何 OPEN 或 ADD 行为",
            "WEAK_VALID 状态下禁止 aggressive_add",
            "若 risk_flags 包含高风险标记，必须强制 risk_bias 为 conservative 或 defensive"
        ],
        "priority": 10
    },

    "market_structure": {
        "role": "Market Structure Expert",
        "description": "刻画多周期市场结构与参与者行为，用于约束交易意图空间。",
        "interpretation": [
            "long_term 结构用于风险否决，不用于短期方向判断。",
            "risk_state 为 high 时，应限制风险扩张行为。",
            "结构冲突时，以高周期为约束优先级。",
            # 当主裁周期呈现 risk_off 行为时，输出应更偏向收敛空间
            "当主裁周期 participant positioning 为 risk_off 时：",
            "不鼓励在同方向继续增加风险暴露",
            "更倾向于保持或减少风险暴露",
            "当 risk_off 与 ATTENUATE 同时存在时：可允许极小幅度、非趋势性风险增加，但整体风险偏好必须保持收敛"
        ],
        "constraints": [
            "long_term 不支持风险扩张时，禁止扩大仓位暴露"
        ],
        "priority": 20
    },

    "position_state": {
        "role": "Position State Expert",
        "description": "描述当前账户持仓状态与风险暴露情况。",
        "interpretation": [
            "position_side 仅描述事实状态，不隐含主观判断。",
            "exposure_level 用于限制决策空间，而非方向选择。"
        ],
        "constraints": [
            "高 exposure_level 下不得叠加同方向风险"
        ],
        "priority": 30
    }
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
        "signal_verdict": {"verdict": "ATTENUATE",
                           "structural_alignment": "PARTIAL_CONFLICT",
                           "risk_implication": "elevated",
                           "reasoning": [
                               "signal_context.dominant_bucket = mid 且 mid_term.participant_positioning.structural_weight = high，表明中期为唯一主裁周期。",
                               "mid_term.participant_positioning.confidence.level = low，主裁周期未提供强方向性支持。",
                               "mid_term.structural_risks.crowding_risk = high，表明中期结构存在风险标记。",
                               "signal_direction = bullish 且 mid_term.participant_positioning.structural_weight = high，该方向未被主裁周期人群定位模式明确支持。",
                               "long_term.structural_weight = veto_only 且 long_term.confidence.level = low，未满足长期否决条件。"]
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
