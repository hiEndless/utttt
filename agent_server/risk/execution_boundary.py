from typing import Dict, List, Optional, Tuple, Any


class ExecutionBoundary:
    """
    确定性聚合器
    提供给持仓风控agent
    职责：
    - 将 SignalValidation + Decision 的结果，转换为【确定性的执行边界】
    - 只回答：哪些动作【绝对不允许】
    - 不对“应该做什么”做任何判断

    明确不做：
    - 不输出 verdict / confidence
    - 不触发 exit / reduce
    - 不评估持仓好坏

    将 信号验证 (SignalValidation) 等 agnet 的客观评估结果与 交易决策 (Decision) 的主观意图进行“对抗性聚合”，生成最终的 执行约束 (Execution Constraint) 。

    它是连接“市场认知”与“持仓风控”的关键桥梁，主要功能包括：
    1. 硬性门控 (Gating) : 当信号验证判定市场结构存在严重冲突时，直接阻断 (BLOCK) 任何开仓或加仓行为。
    2. 信心降权 (Confidence Attenuation) : 当信号质量一般或存在风险时，降低执行置信度，从而触发“减半执行”或“更严格的止损”策略。
    3. 意图修正 (Intent Bias) : 确保交易意图（如“做多”）与大周期方向一致。

    功能更偏向 信号与决策的聚合、生成约束边界。
    输出不仅有 forbidden_actions，还有 allowed_actions、intent_bias、reason_tags。
    主要是 面向风控系统、人工操作，强调可解释性和信号对齐。
    """

    # ------------------------
    # Public API
    # ------------------------

    def aggregate(
        self,
        signal_validation: Dict[str, Any],
        decision_output: Dict[str, Any],
    ) -> Dict[str, Any]:

        forbidden_from_signal = self._derive_signal_forbidden_actions(signal_validation)
        forbidden_from_decision = self._derive_decision_forbidden_actions(decision_output)

        forbidden_actions = self._merge_forbidden(
            forbidden_from_signal,
            forbidden_from_decision,
        )

        allowed_actions = self._derive_allowed_actions(
            decision_output=decision_output,
            forbidden_actions=forbidden_actions,
        )

        intent_bias = self._derive_intent_bias(signal_validation)

        reason_tags = self._derive_reason_tags(
            signal_validation=signal_validation,
            forbidden_actions=forbidden_actions,
        )

        return {
            "execution_constraint": {
                "intent_bias": intent_bias,
                "allowed_actions": allowed_actions,
                "forbidden_actions": forbidden_actions,
                "risk_bias": self._extract_risk_bias(decision_output),
                "constraint_reason_tags": reason_tags,
            }
        }

    # ------------------------
    # Forbidden Actions (Hard Gate)
    # ------------------------

    def _derive_signal_forbidden_actions(
        self, signal_validation: Dict[str, Any]
    ) -> List[str]:
        """
        从 SignalValidation 中提取【必须禁止】的行为
        只处理“结构性 veto / block”级别。

        放宽逻辑（与 Trade Decision 一致）：
        - 仅当「主导周期方向真正冲突」时才禁止 open，避免因短期拥挤/噪音就一刀切。
        - structural_clarity == DOMINANT_CONFLICT 且 dominant_cycle 的 directional_alignment 为 CONFLICT → 禁止 open。
        - structural_clarity == DOMINANT_CONFLICT 但 dominant_cycle 为 ALIGNED/NEUTRAL（例如仅短期拥挤）→ 不禁止 open，交给 Trade Decision 用 5~10x 决定。
        """

        forbidden: List[str] = []

        audit_conf = signal_validation.get("audit_confidence", {})
        structural_clarity = audit_conf.get("structural_clarity")
        audit_breakdown = signal_validation.get("audit_breakdown", {})
        directional_alignment = audit_breakdown.get("directional_alignment") or {}
        dominant_cycle = signal_validation.get("dominant_cycle") or "mid_term"

        # 主导周期方向对齐情况：取 dominant_cycle 对应周期（如 mid_term）的 alignment
        dominant_alignment = (directional_alignment.get(dominant_cycle) or "").upper() if isinstance(directional_alignment, dict) else ""

        if structural_clarity == "DOMINANT_CONFLICT":
            # 仅当「主导周期方向为 CONFLICT」时才禁止 open；否则只禁止激进加仓等，允许 Trade Decision 用低杠杆开仓
            if dominant_alignment == "CONFLICT":
                forbidden += [
                    "open",
                    "aggressive_add",
                    "scale_in_small",
                    "reverse_position",
                ]
            else:
                # 主导周期 ALIGNED/NEUTRAL，仅短期或它周期冲突/拥挤 → 不禁止 open，只禁止激进加仓
                forbidden += ["aggressive_add", "scale_in_small", "reverse_position"]

        risk_flags = signal_validation.get("risk_exposure_flags", [])
        for f in risk_flags:
            if isinstance(f, str) and "crowding_risk_high" in f:
                forbidden += ["aggressive_add"]

        return self._dedupe(forbidden)

    def _derive_decision_forbidden_actions(
        self, decision_output: Dict[str, Any]
    ) -> List[str]:

        trade_intent = decision_output.get("trade_intent_range", {}) or {}
        forbidden = trade_intent.get("forbidden_actions", []) or []

        return self._dedupe(forbidden)

    # ------------------------
    # Allowed Actions（弱定义）
    # ------------------------

    def _derive_allowed_actions(
        self,
        decision_output: Dict[str, Any],
        forbidden_actions: List[str],
    ) -> List[str]:
        """
        allowed_actions 只做一件事：
        - 从 decision 中继承
        - 移除 forbidden
        """

        trade_intent = decision_output.get("trade_intent_range", {}) or {}
        allowed = trade_intent.get("allowed_actions", []) or []

        allowed_clean = [
            a for a in self._dedupe(allowed)
            if a not in forbidden_actions
        ]

        return allowed_clean

    # ------------------------
    # Intent Bias（仅语义提示）
    # ------------------------

    def _derive_intent_bias(
        self, signal_validation: Dict[str, Any]
    ) -> Optional[str]:

        direction = (
            (signal_validation.get("meta", {}) or {}).get("direction")
            or signal_validation.get("direction")
        )

        if not direction:
            return None

        return str(direction).strip().lower()

    # ------------------------
    # Reason Tags（Explain Only）
    # ------------------------

    def _derive_reason_tags(
        self,
        signal_validation: Dict[str, Any],
        forbidden_actions: List[str],
    ) -> List[str]:

        tags: List[str] = []

        audit_conf = signal_validation.get("audit_confidence", {})
        if audit_conf.get("structural_clarity") == "DOMINANT_CONFLICT" and "open" in forbidden_actions:
            tags.append("dominant_structural_conflict")

        if any(a in forbidden_actions for a in ("aggressive_add", "scale_in_small")):
            tags.append("risk_exposure_restricted")

        return tags

    # ------------------------
    # Utilities
    # ------------------------

    @staticmethod
    def _extract_risk_bias(decision_output: Dict[str, Any]) -> Optional[str]:
        trade_intent = decision_output.get("trade_intent_range", {}) or {}
        return trade_intent.get("risk_bias")

    @staticmethod
    def _dedupe(actions: List[Any]) -> List[str]:
        out = []
        seen = set()
        for a in actions:
            if not a:
                continue
            s = str(a).strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out

    @staticmethod
    def _merge_forbidden(*lists: List[str]) -> List[str]:
        merged: List[str] = []
        for lst in lists:
            merged += lst
        return list(dict.fromkeys(merged))


if __name__ == "__main__":
    aggregator = ExecutionBoundary()

    # V2 Test Data
    signal_validation = {'dominant_cycle': 'mid_term',
                         'cycle_weights': {'short_term': 'low', 'mid_term': 'high', 'long_term': 'veto_only'},
                         'audit_breakdown': {'directional_alignment': {'short_term': 'CONFLICT', 'mid_term': 'CONFLICT',
                                                                       'long_term': 'NEUTRAL'},
                                             'leverage_phase_match': {'short_term': 'MATCH', 'mid_term': 'MATCH',
                                                                      'long_term': 'NOT_APPLICABLE'}},
                         'conflict_evidence': {'directional_conflict': [
                             '交易方向为向下（SHORT），但中期价格趋势为上涨（price_trend=up）且中期参与者行为为做多建仓（behavior=directional_building），构成方向性冲突',
                             '短期价格趋势为下跌（price_trend=down），但短期主动买卖盘偏差为中性（taker_bias=neutral），而交易行为仍选择增加空头敞口，与短期结构缺乏明确支持信号形成张力'],
                                               'leverage_conflict': []}, 'risk_exposure_flags': ['crowding_risk_high'],
                         'audit_confidence': {'level': 'MEDIUM', 'structural_clarity': 'DOMINANT_CONFLICT'},
                         'meta': {'symbol': 'ETHUSDT', 'exchange': 'binance',
                                  'event_id': 'binance.ETHUSDT.trade.decrease.1770992681156',
                                  'event_type': 'trade.decrease', 'trade_id': '654b1eaf03bd4cc2bd09cc62ce879596',
                                  'direction': 'bullish', 'ts': 1770992695078, 'version': 'v1.2',
                                  'name': 'trade_behavior'}, 'positions': [
            {'symbol': 'ETHUSDT', 'position_side': 'SHORT', 'size': '-0.031', 'notional': '-60.99865626',
             'pnl_ratio': -0.043254017547924246, 'open_time': 1770969387424,
             'trade_id': '654b1eaf03bd4cc2bd09cc62ce879596', 'initialMargin': '12.19973126', 'leverage': 5}]}

    decision_output = {"trade_intent_range": {"allowed_actions": ["hold", "reduce"],
                                              "forbidden_actions": ["aggressive_add", "reverse_position",
                                                                    "scale_in_small"], "risk_bias": "defensive"},
                       "reasoning": [
                           "根据 Trade Behavior Audit Expert 输入，dominant_cycle 为 mid_term 且处于 CONFLICT 状态（directional_alignment.mid_term = CONFLICT），依据约束‘若 dominant_cycle 处于 CONFLICT 状态，禁止激进追涨杀跌’，应禁止任何加仓行为，包括 small scale-in。",
                           "cycle_weights 显示 long_term 为 veto_only，且 directional_alignment.long_term = NEUTRAL，虽未直接否决，但结合 mid_term 高权重且存在方向性冲突（中期趋势上涨但当前持仓为 SHORT），构成结构性逆势，依据‘high 权重周期 veto_only 且 directional_alignment 为 CONFLICT 时禁止同向开仓’的保守原则，进一步限制新增空头暴露。",
                           "audit_confidence.structural_clarity = DOMINANT_CONFLICT，触发‘应触发防御性策略’的规则；同时 risk_exposure_flags 包含 crowding_risk_high，强化了收缩风险敞口的必要性。",
                           "position_state 显示当前为 small 规模的亏损空头持仓（pnl_state: loss, holding_bias: against），在结构冲突与高拥挤风险下，最优动作为减仓或持有观望，而非维持或扩大暴露。因此 allowed_actions 仅保留 hold 与 reduce，明确排除 scale_in_small。"],
                       "meta": {"symbol": "ETHUSDT", "exchange": "binance",
                                "event_id": "binance.ETHUSDT.trade.decrease.1770992681156",
                                "trade_id": "654b1eaf03bd4cc2bd09cc62ce879596", "ts": 1770992695086, "version": "v1.0",
                                "name": "decision"}}

    result = aggregator.aggregate(signal_validation, decision_output)
    print(result)
