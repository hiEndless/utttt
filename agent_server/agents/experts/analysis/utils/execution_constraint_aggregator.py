from typing import Dict, List, Optional, Tuple, Any


class ExecutionConstraintAggregator:
    """
    确定性聚合器：将 SignalValidation + Decision 的输出合成为 execution_constraint。
    提供给持仓风控agent

    将 信号验证 (SignalValidation) 等 agnet 的客观评估结果与 交易决策 (Decision) 的主观意图进行“对抗性聚合”，生成最终的 执行约束 (Execution Constraint) 。

    它是连接“市场认知”与“持仓风控”的关键桥梁，主要功能包括：
    1. 硬性门控 (Gating) : 当信号验证判定市场结构存在严重冲突时，直接阻断 (BLOCK) 任何开仓或加仓行为。
    2. 信心降权 (Confidence Attenuation) : 当信号质量一般或存在风险时，降低执行置信度，从而触发“减半执行”或“更严格的止损”策略。
    3. 意图修正 (Intent Bias) : 确保交易意图（如“做多”）与大周期方向一致。
    """

    BASE_CONFIDENCE = 0.75

    VERDICT_PENALTY = {
        "ALLOW": 0.0,
        "ATTENUATE": -0.15,
        "BLOCK": -0.55,
    }

    STRUCTURAL_ALIGNMENT_PENALTY = {
        "ALIGNED": 0.0,
        "PARTIAL_CONFLICT": -0.10,
        "STRONG_CONFLICT": -0.25
    }

    RISK_IMPLICATION_PENALTY = {
        "none": 0.0,
        "normal": 0.0,
        "elevated": -0.05,
        "high": -0.15
    }

    def aggregate(
            self,
            signal_validation: Dict,
            decision_output: Dict
    ) -> Dict:
        """
        Aggregate SignalValidation V2 output with Decision output.
        V1 format is no longer supported.
        """

        # Extract core metrics from V2 structure
        structural_alignment = self._derive_structural_alignment(signal_validation)
        risk_implication = self._derive_risk_implication(signal_validation)
        verdict = self._derive_verdict(signal_validation, structural_alignment, risk_implication)

        # Decision output processing
        trade_intent = decision_output.get("trade_intent_range", {})
        allowed_actions = list(trade_intent.get("allowed_actions", []) or [])
        forbidden_actions = list(trade_intent.get("forbidden_actions", []) or [])
        risk_bias = trade_intent.get("risk_bias")
        # decision_rationale = list(decision_output.get("decision_rationale", []) or [])

        # Apply gate
        allowed_actions_effective, forbidden_actions_effective = self._apply_verdict_gate(
            verdict=verdict,
            allowed_actions=allowed_actions,
            forbidden_actions=forbidden_actions,
        )

        intent_bias = self._derive_intent_bias(
            signal_validation=signal_validation,
            verdict=verdict,
            risk_bias=risk_bias
        )

        confidence = self._derive_confidence(
            verdict=verdict,
            structural_alignment=structural_alignment,
            risk_implication=risk_implication
        )

        constraint_reason_tags = self._derive_reason_tags(
            verdict=verdict,
            structural_alignment=structural_alignment,
            risk_implication=risk_implication
        )

        return {
            "execution_constraint": {
                "intent_bias": intent_bias,
                "allowed_actions": allowed_actions_effective,
                "forbidden_actions": forbidden_actions_effective,
                "risk_bias": risk_bias,
                "confidence": confidence,
                "constraint_reason_tags": constraint_reason_tags,
            }
        }

    # ------------------------
    # Derivation methods (V2)
    # ------------------------

    def _derive_structural_alignment(self, sv: Dict) -> str:
        """
        Derive structural alignment from V2 audit breakdown.
        Returns: ALIGNED / PARTIAL_CONFLICT / STRONG_CONFLICT
        """
        audit_confidence = sv.get("audit_confidence", {})
        audit_breakdown = sv.get("audit_breakdown", {})
        structural_clarity = audit_confidence.get("structural_clarity")

        dir_align = audit_breakdown.get("directional_alignment", {})
        lev_match = audit_breakdown.get("leverage_phase_match", {})

        # Priority 1: Dominant/Strong Conflict
        if structural_clarity == "DOMINANT_CONFLICT":
            return "STRONG_CONFLICT"
        if dir_align.get("mid_term") == "CONFLICT":
            return "STRONG_CONFLICT"

        # Priority 2: Partial Conflict
        if dir_align.get("mid_term") == "NEUTRAL":
            return "PARTIAL_CONFLICT"
        if lev_match.get("mid_term") == "MISMATCH":
            return "PARTIAL_CONFLICT"

        return "ALIGNED"

    def _derive_risk_implication(self, sv: Dict) -> str:
        """
        Derive risk implication from V2 risk flags.
        Returns: none / elevated / high
        """
        risk_flags = sv.get("risk_exposure_flags", [])

        has_high_risk = False
        has_vacuum = False

        for f in risk_flags:
            if isinstance(f, dict):
                val = str(f.get("value", "")).lower()
                if val == "high":
                    has_high_risk = True
                
                if f.get("type") == "liquidity_vacuum" and (
                    f.get("value") is True or val == "true"
                ):
                    has_vacuum = True
            elif isinstance(f, str):
                s = str(f).lower()
                if "high" in s:
                    has_high_risk = True
                if "liquidity_vacuum" in s:
                    has_vacuum = True

        if has_high_risk:
            return "high"
        if has_vacuum:
            return "elevated"

        return "none"

    def _derive_verdict(self, sv: Dict, alignment: str, risk: str) -> str:
        """
        Derive final verdict.
        Returns: ALLOW / ATTENUATE / BLOCK
        """
        audit_confidence = sv.get("audit_confidence", {})
        confidence_level = audit_confidence.get("level", "HIGH")

        if alignment == "STRONG_CONFLICT":
            return "BLOCK"

        # High risk usually attenuates rather than blocks (unless combined with conflict)
        if risk == "high":
            return "ATTENUATE"

        if confidence_level == "LOW":
            return "ATTENUATE"

        if alignment == "PARTIAL_CONFLICT":
            return "ATTENUATE"

        return "ALLOW"

    @staticmethod
    def _dedupe_actions(actions: List[Any]) -> List[str]:
        out: List[str] = []
        seen = set()
        for a in list(actions or []):
            if a is None:
                continue
            s = str(a).strip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    def _apply_verdict_gate(
            self,
            verdict: Optional[str],
            allowed_actions: List[Any],
            forbidden_actions: List[Any],
    ) -> Tuple[List[str], List[str]]:
        """
        将 SignalValidation 的 verdict 转换为“可执行动作门控”：
        - BLOCK：禁止所有动作（allowed 置空，原 allowed 并入 forbidden）
        - 其他：保持 Decision 输出不变（仅做去重与清洗）
        """
        allowed = self._dedupe_actions(allowed_actions)
        forbidden = self._dedupe_actions(forbidden_actions)

        if verdict == "BLOCK":
            return [], self._dedupe_actions(forbidden + allowed)
        return allowed, forbidden

    def _derive_intent_bias(
            self,
            signal_validation: Dict,
            verdict: Optional[str],
            risk_bias: Optional[str]
    ) -> Optional[str]:

        direction = (
                (signal_validation.get("meta", {}) or {}).get("direction")
                or signal_validation.get("direction")
        )
        direction = str(direction).strip().lower() if direction else None
        risk_bias_norm = str(risk_bias).strip().lower() if risk_bias else None

        if not direction or not verdict or not risk_bias_norm:
            return None

        if verdict == "ATTENUATE":
            if direction in {"bullish", "bearish"}:
                return f"{direction}_but_attenuated"
            return "attenuated"

        if verdict == "ALLOW":
            return direction

        return None

    def _derive_confidence(
            self,
            verdict: str,
            structural_alignment: str,
            risk_implication: str
    ) -> float:
        confidence = self.BASE_CONFIDENCE

        confidence += self.VERDICT_PENALTY.get(verdict, 0.0)
        confidence += self.STRUCTURAL_ALIGNMENT_PENALTY.get(structural_alignment, 0.0)
        confidence += self.RISK_IMPLICATION_PENALTY.get(risk_implication, 0.0)

        return max(0.0, min(round(confidence, 2), 1.0))

    def _derive_reason_tags(
            self,
            verdict: str,
            structural_alignment: str,
            risk_implication: str
    ) -> List[str]:
        tags = []

        if verdict == "ATTENUATE":
            tags.append("signal_attenuated")
        elif verdict == "BLOCK":
            tags.append("signal_blocked")

        if structural_alignment == "PARTIAL_CONFLICT":
            tags.append("partial_structural_conflict")
        elif structural_alignment == "STRONG_CONFLICT":
            tags.append("strong_structural_conflict")

        if risk_implication and risk_implication != "none":
            tags.append(f"risk_{risk_implication}")

        return tags


if __name__ == "__main__":
    aggregator = ExecutionConstraintAggregator()

    # V2 Test Data
    signal_validation = {"dominant_cycle": "mid_term",
                         "cycle_weights": {"short_term": "low", "mid_term": "high", "long_term": "veto_only"},
                         "audit_breakdown": {"directional_alignment": {"short_term": "CONFLICT", "mid_term": "CONFLICT",
                                                                       "long_term": "NEUTRAL"},
                                             "leverage_phase_match": {"short_term": "MATCH", "mid_term": "MISMATCH",
                                                                      "long_term": "NOT_APPLICABLE"}},
                         "conflict_evidence": {"directional_conflict": [
                             "交易方向为向下（SHORT），但中期价格趋势为上涨（price_trend=up）且参与者行为推断为对冲（behavior=hedging），表明市场中期结构不支持主动做空。",
                             "短期价格趋势为下跌（price_trend=down），但主动买卖盘偏差为多头（taker_bias=long），与交易方向（SHORT）存在结构性背离。"],
                                               "leverage_conflict": [
                                                   "中期市场处于杠杆扩张阶段（oi_acceleration=accelerating_up，positioning_mode=neutral），而交易行为为增加向下敞口（exposure_change=INCREASE），与当前风险扩张（risk_regime=EXPANSION）下的杠杆周期不匹配。"]},
                         "risk_exposure_flags": ["crowding_risk_high", "structure_divergence"],
                         "audit_confidence": {"level": "MEDIUM", "structural_clarity": "RISK_CLUSTER_PRESENT"},
                         "meta": {"symbol": "ETHUSDT", "exchange": "binance",
                                  "event_id": "binance.ETHUSDT.trade.decrease.1770982287012",
                                  "event_type": "trade.decrease", "trade_id": "654b1eaf03bd4cc2bd09cc62ce879596",
                                  "direction": "bullish", "ts": 1770982298766, "version": "v1.2",
                                  "name": "trade_behavior"}, "positions": [
            {"symbol": "ETHUSDT", "position_side": "SHORT", "size": "-0.037", "notional": "-72.13335000",
             "pnl_ratio": 0.0028889099147620346, "open_time": 1770969387424,
             "trade_id": "654b1eaf03bd4cc2bd09cc62ce879596", "initialMargin": "14.42667000"}]}

    decision_output = {"trade_intent_range": {"allowed_actions": ["hold", "reduce"],
                                              "forbidden_actions": ["aggressive_add", "scale_in_small",
                                                                    "reverse_position"], "risk_bias": "defensive"},
                       "reasoning": [
                           "Signal Validation Expert 指出存在 'crowding_risk' 高风险标记（重复出现），根据约束规则，必须将 risk_bias 设为 defensive 或 conservative；结合当前已有亏损的空头仓位，优先选择 defensive。",
                           "尽管 dominant_cycle 为 short_term 且 directional_alignment 为 ALIGNED，但 cycle_weights 显示 short_term 权重为 low，而 mid_term 权重为 high 且处于 NEUTRAL 状态，缺乏结构强化支持，不构成激进操作依据。",
                           "audit_confidence.level 为 MEDIUM，structural_clarity 为 RISK_CLUSTER_PRESENT，表明信号虽非无效，但伴随显著风险聚集，禁止任何加仓行为（包括 scale_in_small）。",
                           "当前持仓为 small 规模的亏损空单，position_state 显示 holding_bias 为 neutral，无反转或加仓动机；在 crowding_risk 和 risk_cluster 共存下，最优策略是保持或减仓，避免扩大风险暴露。"],
                       "meta": {"symbol": "ETHUSDT", "exchange": "binance", "event_id": "ETHUSDT.final.1770981758365",
                                "trade_id": "654b1eaf03bd4cc2bd09cc62ce879596", "ts": 1770981806056, "version": "v1.0"}}

    result = aggregator.aggregate(signal_validation, decision_output)
    print(result)
