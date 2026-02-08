from typing import Dict, List, Optional, Tuple, Any


class ExecutionConstraintAggregator:
    """
    确定性聚合器：将 SignalValidation + Decision 的输出合成为 execution_constraint。
    提供给持仓风控agent
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
        trade_intent = decision_output.get("trade_intent_range", {})

        allowed_actions = list(trade_intent.get("allowed_actions", []) or [])
        forbidden_actions = list(trade_intent.get("forbidden_actions", []) or [])
        risk_bias = trade_intent.get("risk_bias")
        decision_rationale = list(decision_output.get("decision_rationale", []) or [])

        verdict = self._normalize_verdict(signal_validation.get("verdict"))
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

        confidence = self._derive_confidence(signal_validation, verdict=verdict)

        constraint_reason_tags = self._derive_reason_tags(signal_validation, verdict=verdict)

        signal_reasoning = signal_validation.get("reasoning")
        if not isinstance(signal_reasoning, list):
            signal_reasoning = []

        return {
            "execution_constraint": {
                "intent_bias": intent_bias,
                "allowed_actions": allowed_actions_effective,
                "forbidden_actions": forbidden_actions_effective,
                "risk_bias": risk_bias,
                "confidence": confidence,
                "constraint_reason_tags": constraint_reason_tags,
                # "rationale": {
                #     "signal_validation_reasoning": signal_reasoning,
                #     "decision_rationale": decision_rationale,
                # },
            }
        }

    # ------------------------
    # Derivation methods
    # ------------------------

    @staticmethod
    def _normalize_verdict(verdict: Any) -> Optional[str]:
        """
        统一 verdict 口径：
        - 新：ALLOW / ATTENUATE / BLOCK
        - 旧：VALID / WEAK_VALID / INVALID
        """
        if verdict is None:
            return None
        v = str(verdict).strip().upper()
        mapping = {
            "ALLOW": "ALLOW",
            "VALID": "ALLOW",
            "ATTENUATE": "ATTENUATE",
            "WEAK_VALID": "ATTENUATE",
            "BLOCK": "BLOCK",
            "INVALID": "BLOCK",
        }
        return mapping.get(v)

    @staticmethod
    def _normalize_structural_alignment(alignment: Any) -> Optional[str]:
        """
        统一 structural_alignment 口径：
        - 新：ALIGNED / PARTIAL_CONFLICT / STRONG_CONFLICT
        - 旧：ALIGNED / CONFLICT / STRONGLY_CONFLICT
        """
        if alignment is None:
            return None
        a = str(alignment).strip().upper()
        mapping = {
            "ALIGNED": "ALIGNED",
            "PARTIAL_CONFLICT": "PARTIAL_CONFLICT",
            "STRONG_CONFLICT": "STRONG_CONFLICT",
            "CONFLICT": "PARTIAL_CONFLICT",
            "STRONGLY_CONFLICT": "STRONG_CONFLICT",
        }
        return mapping.get(a, None)

    @staticmethod
    def _normalize_risk_implication(risk: Any) -> Optional[str]:
        """
        统一 risk_implication 口径：
        - 新：none / elevated
        - 旧：normal / elevated / high
        """
        if risk is None:
            return None
        r = str(risk).strip().lower()
        if r in {"none", "normal"}:
            return "none"
        if r in {"elevated", "high"}:
            return r
        return None

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

    def _derive_confidence(self, signal_validation: Dict, verdict: Optional[str]) -> float:
        confidence = self.BASE_CONFIDENCE

        structural_alignment = self._normalize_structural_alignment(
            signal_validation.get("structural_alignment")
        )
        risk_implication = self._normalize_risk_implication(
            signal_validation.get("risk_implication")
        )

        confidence += self.VERDICT_PENALTY.get(verdict, 0.0)
        confidence += self.STRUCTURAL_ALIGNMENT_PENALTY.get(structural_alignment, 0.0)
        confidence += self.RISK_IMPLICATION_PENALTY.get(risk_implication, 0.0)

        return max(0.0, min(round(confidence, 2), 1.0))

    def _derive_reason_tags(self, signal_validation: Dict, verdict: Optional[str]) -> List[str]:
        tags = []

        structural_alignment = self._normalize_structural_alignment(
            signal_validation.get("structural_alignment")
        )
        risk_implication = self._normalize_risk_implication(
            signal_validation.get("risk_implication")
        )

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

    signal_validation = {
        "verdict": "ATTENUATE",
        "structural_alignment": "PARTIAL_CONFLICT",
        "risk_implication": "elevated",
        "reasoning": ["多周期结构存在轻度冲突，建议降低仓位与加仓强度"],
        "meta": {
            "direction": "bullish"
        }
    }

    decision_output = {
        "trade_intent_range": {
            "allowed_actions": ["hold", "reduce", "scale_in_small"],
            "forbidden_actions": ["aggressive_add", "reverse_position"],
            "risk_bias": "conservative"
        },
        "decision_rationale": ["4h/1d 结构偏多但短周期流动性不稳，建议保守执行"],
    }

    result = aggregator.aggregate(signal_validation, decision_output)
    print(result)
