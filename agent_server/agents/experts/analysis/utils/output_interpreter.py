import json
from typing import Dict, Any, List, Union


class AgentOutputInterpreter:
    """
    专门用于解析 Analysis Expert Agents 输出的 JSON 内容，
    并将其转换为易读的自然语言描述（支持多语言）。
    支持 SignalValidation, TradeEvent, PositionRisk 等 Agent。
    """

    # 静态语言包定义
    LANG_PACK = {
        "zh": {
            "reasoning_none": "无具体原因说明。",
            "reasoning_title": "详细原因：",
            "unknown": "未知",

            # Signal Validation
            "sv_title": "【信号验证分析】",
            "sv_verdict": "📊 结论",
            "sv_alignment": "🔗 结构一致性",
            "sv_conf_adj": "📉 置信度调整",
            "sv_verdict_map": {
                "VALID": "✅ 有效 (VALID)",
                "WEAK_VALID": "⚠️ 弱有效 (WEAK_VALID)",
                "INVALID": "❌ 无效 (INVALID)"
            },
            "sv_alignment_map": {
                "ALIGNED": "一致",
                "CONFLICT": "存在冲突",
                "STRONGLY_CONFLICT": "严重冲突"
            },
            "sv_conf_adj_map": {
                "none": "保持不变",
                "down": "建议下调"
            },

            # Trade Event
            "te_title": "【交易事件评估】",
            "te_verdict": "⚖️ 评估结果",
            "te_alignment": "🌍 市场背景",
            "te_conf_adj": "🔍 置信度建议",
            "te_verdict_map": {
                "VALID": "✅ 交易机会有效 (VALID)",
                "WEAK_VALID": "⚠️ 交易机会弱有效 (WEAK_VALID)",
                "INVALID": "❌ 交易机会无效 (INVALID)"
            },
            "te_alignment_map": {
                "ALIGNED": "与市场背景一致",
                "CONFLICT": "与市场背景冲突",
                "STRONGLY_CONFLICT": "与市场背景严重冲突"
            },
            "te_conf_adj_map": {
                "none": "不建议调整",
                "down": "建议下调"
            },

            # Position Risk
            "pr_title": "【持仓风险风控】",
            "pr_risk_state": "🌡️ 当前风险等级",
            "pr_action": "💡 风控建议",
            "pr_max_exposure": "📊 最大允许仓位",
            "pr_tighten_stop": "🛡️ 收紧止损",
            "pr_freeze": "🧊 加仓冻结",
            "pr_risk_map": {
                "LOW": "🟢 低风险 (LOW)",
                "MEDIUM": "🟡 中等风险 (MEDIUM)",
                "HIGH": "🟠 高风险 (HIGH)",
                "CRITICAL": "🔴 极高风险 (CRITICAL)"
            },
            "pr_action_map": {
                "ADD_POSITION": "➕ 建议加仓",
                "HOLD": "✊ 建议持有",
                "DEFENSIVE": "🛡️ 建议防御 (不加仓/收紧止损)",
                "REDUCE": "📉 建议减仓",
                "EXIT": "🚫 建议清仓"
            },
            "pr_tighten_yes": "✅ 是",
            "pr_tighten_no": "❌ 否",
            "pr_add": "加仓",
            "pr_reduce": "减仓",
            "min_suffix": "分钟"
        },
        "en": {
            "reasoning_none": "No specific reasons provided.",
            "reasoning_title": "Reasoning:",
            "unknown": "UNKNOWN",

            # Signal Validation
            "sv_title": "[Signal Validation Analysis]",
            "sv_verdict": "📊 Verdict",
            "sv_alignment": "🔗 Structural Alignment",
            "sv_conf_adj": "📉 Confidence Adjustment",
            "sv_verdict_map": {
                "VALID": "✅ VALID",
                "WEAK_VALID": "⚠️ WEAK_VALID",
                "INVALID": "❌ INVALID"
            },
            "sv_alignment_map": {
                "ALIGNED": "ALIGNED",
                "CONFLICT": "CONFLICT",
                "STRONGLY_CONFLICT": "STRONGLY CONFLICT"
            },
            "sv_conf_adj_map": {
                "none": "None",
                "down": "Adjust Down"
            },

            # Trade Event
            "te_title": "[Trade Event Assessment]",
            "te_verdict": "⚖️ Verdict",
            "te_alignment": "🌍 Market Context",
            "te_conf_adj": "🔍 Confidence Suggestion",
            "te_verdict_map": {
                "VALID": "✅ Valid Opportunity",
                "WEAK_VALID": "⚠️ Weak Valid Opportunity",
                "INVALID": "❌ Invalid Opportunity"
            },
            "te_alignment_map": {
                "ALIGNED": "Aligned with Context",
                "CONFLICT": "Conflict with Context",
                "STRONGLY_CONFLICT": "Strongly Conflict with Context"
            },
            "te_conf_adj_map": {
                "none": "No Adjustment",
                "down": "Adjust Down"
            },

            # Position Risk
            "pr_title": "[Position Risk Control]",
            "pr_risk_state": "🌡️ Risk Level",
            "pr_action": "💡 Recommendation",
            "pr_max_exposure": "📊 Max Exposure",
            "pr_tighten_stop": "🛡️ Tighten Stop",
            "pr_freeze": "🧊 Freeze Adding",
            "pr_risk_map": {
                "LOW": "🟢 LOW",
                "MEDIUM": "🟡 MEDIUM",
                "HIGH": "🟠 HIGH",
                "CRITICAL": "🔴 CRITICAL"
            },
            "pr_action_map": {
                "ADD_POSITION": "➕ ADD POSITION",
                "HOLD": "✊ HOLD",
                "DEFENSIVE": "🛡️ DEFENSIVE",
                "REDUCE": "📉 REDUCE",
                "EXIT": "🚫 EXIT"
            },
            "pr_tighten_yes": "✅ Yes",
            "pr_tighten_no": "❌ No",
            "pr_add": "Add",
            "pr_reduce": "Reduce",
            "min_suffix": "mins"
        }
    }

    @staticmethod
    def _get_lang_text(lang: str, key: str, default: str = "") -> str:
        """获取指定语言的文本，默认为中文"""
        lang_pack = AgentOutputInterpreter.LANG_PACK.get(lang, AgentOutputInterpreter.LANG_PACK["zh"])
        return lang_pack.get(key, default)

    @staticmethod
    def interpret(agent_name: str, output: Union[Dict[str, Any], str], language: str = "zh") -> str:
        """
        通用解析入口。
        :param agent_name: agent 名称 (signal_validation, trade_event, position_risk)
        :param output: agent 输出的字典或 JSON 字符串
        :param language: 目标语言代码 ('zh', 'en')，默认为 'zh'
        :return: 格式化后的自然语言字符串
        """
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                return f"JSON Parse Error: {output}"

        # 尝试从 output 中推断语言（如果 output 包含 language 字段）
        # 但通常解释器的语言由调用者决定，这里保留参数控制优先

        if agent_name == "signal_validation":
            return AgentOutputInterpreter.interpret_signal_validation(output, language)
        elif agent_name == "trade_event":
            return AgentOutputInterpreter.interpret_trade_event(output, language)
        elif agent_name == "position_risk":
            return AgentOutputInterpreter.interpret_position_risk(output, language)
        else:
            return f"Unknown Agent: {agent_name}"

    @staticmethod
    def _format_reasoning(reasons: List[str], language: str = "zh") -> str:
        if not reasons:
            return AgentOutputInterpreter._get_lang_text(language, "reasoning_none")
        formatted = "\n".join([f"  • {r}" for r in reasons])
        title = AgentOutputInterpreter._get_lang_text(language, "reasoning_title")
        return f"\n{title}\n{formatted}"

    @staticmethod
    def interpret_signal_validation(output: Dict[str, Any], language: str = "zh") -> str:
        """解析 SignalValidationExpert 的输出"""
        lt = lambda k: AgentOutputInterpreter._get_lang_text(language, k)

        verdict_raw = output.get("verdict", "UNKNOWN")
        verdict = lt("sv_verdict_map").get(verdict_raw, verdict_raw)

        alignment_raw = output.get("alignment", "UNKNOWN")
        alignment = lt("sv_alignment_map").get(alignment_raw, alignment_raw)

        conf_adj_raw = output.get("confidence_adjustment", "UNKNOWN")
        conf_adj = lt("sv_conf_adj_map").get(conf_adj_raw, conf_adj_raw)

        reasoning = output.get("reasoning", [])

        summary = (
            f"{lt('sv_title')}\n"
            f"{lt('sv_verdict')}：{verdict}\n"
            f"{lt('sv_alignment')}：{alignment}\n"
            f"{lt('sv_conf_adj')}：{conf_adj}"
        )
        return summary + AgentOutputInterpreter._format_reasoning(reasoning, language)

    @staticmethod
    def interpret_trade_event(output: Dict[str, Any], language: str = "zh") -> str:
        """解析 TradeEventExpert 的输出"""
        lt = lambda k: AgentOutputInterpreter._get_lang_text(language, k)

        verdict_raw = output.get("verdict", "UNKNOWN")
        verdict = lt("te_verdict_map").get(verdict_raw, verdict_raw)

        alignment_raw = output.get("alignment", "UNKNOWN")
        alignment = lt("te_alignment_map").get(alignment_raw, alignment_raw)

        conf_adj_raw = output.get("confidence_adjustment", "UNKNOWN")
        conf_adj = lt("te_conf_adj_map").get(conf_adj_raw, conf_adj_raw)

        reasoning = output.get("reasoning", [])

        summary = (
            f"{lt('te_title')}\n"
            f"{lt('te_verdict')}：{verdict}\n"
            f"{lt('te_alignment')}：{alignment}\n"
            f"{lt('te_conf_adj')}：{conf_adj}"
        )
        return summary + AgentOutputInterpreter._format_reasoning(reasoning, language)

    @staticmethod
    def interpret_position_risk(output: Dict[str, Any], language: str = "zh") -> str:
        """解析 PositionRiskExpert 的输出"""
        lt = lambda k: AgentOutputInterpreter._get_lang_text(language, k)

        # 字段兼容处理
        risk_state_raw = output.get("risk_state") or output.get("verdict") or "UNKNOWN"
        action_raw = output.get("recommended_action") or output.get("suggestion") or "UNKNOWN"
        reasoning = output.get("reason_tags") or output.get("reasoning") or []

        risk_state = lt("pr_risk_map").get(risk_state_raw, risk_state_raw)
        action = lt("pr_action_map").get(action_raw, action_raw)

        tighten_stop = lt("pr_tighten_yes") if output.get("tighten_stop") else lt("pr_tighten_no")
        freeze_min = output.get("freeze_add_position_min", 0)

        # 构建操作详情
        action_details = []
        if output.get("add_pct") and output.get("add_pct") > 0:
            action_details.append(f"{lt('pr_add')} {output['add_pct'] * 100:.1f}%")
        if output.get("reduce_pct") and output.get("reduce_pct") > 0:
            action_details.append(f"{lt('pr_reduce')} {output['reduce_pct'] * 100:.1f}%")

        action_detail_str = f" ({', '.join(action_details)})" if action_details else ""

        summary = (
            f"{lt('pr_title')}\n"
            f"{lt('pr_risk_state')}：{risk_state}\n"
            f"{lt('pr_action')}：{action}{action_detail_str}\n"
            f"{lt('pr_tighten_stop')}：{tighten_stop}\n"
            f"{lt('pr_freeze')}：{freeze_min} {lt('min_suffix')}"
        )
        return summary + AgentOutputInterpreter._format_reasoning(reasoning, language)


if __name__ == "__main__":
    # 测试代码
    print("--- Testing Signal Validation (Chinese) ---")
    sv_output = {"verdict": "INVALID", "alignment": "STRONGLY_CONFLICT", "confidence_adjustment": "down",
                 "reasoning": ["多个关键周期（15m、30m）的技术验证结论为冲突，构成结构性不支持。", "市场背景中长期趋势为下跌且具有否决权，与信号隐含前提形成根本性冲突。",
                               "人群博弈呈现与信号方向一致的拥挤状态，且稳定性不足，存在非线性风险与资金挤压风险。"]}

    print(AgentOutputInterpreter.interpret("signal_validation", sv_output, "zh"))
    print("\n")

    print("--- Testing Position Risk (English) ---")
    pr_output = {"risk_state": "CRITICAL", "recommended_action": "EXIT", "reduce_pct": 1.0,
                 "add_pct": 0.0, "tighten_stop": False, "freeze_add_position_min": 0,
                 "reason_tags": ["信号失效", "人群博弈风险", "资金挤压风险", "市场脆弱性高", "结构不支持", "连续验证失败"], "suggestion": "EXIT",
                 "verdict": "CRITICAL", "reasoning": ["信号失效", "人群博弈风险", "资金挤压风险", "市场脆弱性高", "结构不支持", "连续验证失败"]}

    print(AgentOutputInterpreter.interpret("position_risk", pr_output, "zh"))
