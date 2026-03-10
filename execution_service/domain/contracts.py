from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Mapping, Optional


DirectionIntent = Literal["long", "short", "none"]
ConfidenceLevel = Literal["low", "medium", "high"]
ExecutionAction = Literal["add", "reduce", "hold", "exit", "skip"]


@dataclass(frozen=True)
class DecisionConfidence:
    """决策置信度。"""

    level: ConfidenceLevel
    score: float

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DecisionConfidence":
        level = str(payload.get("level", "")).strip().lower()
        score_raw = payload.get("score", 0.0)
        score = float(score_raw)
        if level not in {"low", "medium", "high"}:
            raise ValueError("confidence.level 必须是 low/medium/high")
        if score < 0.0 or score > 1.0:
            raise ValueError("confidence.score 必须在 [0, 1] 区间")
        return cls(level=level, score=score)

    def to_dict(self) -> Dict[str, Any]:
        return {"level": self.level, "score": self.score}


@dataclass(frozen=True)
class DecisionIntent:
    """agent 下发给 execution 的输入契约（v1）。"""

    decision_id: str
    exchange: str
    account_id: str
    symbol: str
    direction_intent: DirectionIntent
    confidence: DecisionConfidence
    cross_horizon_policy: Dict[str, Any]
    risk_hints: Dict[str, Any]
    trace_id: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DecisionIntent":
        decision_id = str(payload.get("decision_id", "")).strip()
        exchange = str(payload.get("exchange", "")).strip()
        account_id = str(payload.get("account_id", "")).strip() or "main"
        symbol = str(payload.get("symbol", "")).strip()
        direction = str(payload.get("direction_intent", "")).strip().lower()
        if not decision_id:
            raise ValueError("decision_id 不能为空")
        if not exchange:
            raise ValueError("exchange 不能为空")
        if not symbol:
            raise ValueError("symbol 不能为空")
        if direction not in {"long", "short", "none"}:
            raise ValueError("direction_intent 必须是 long/short/none")

        confidence_raw = payload.get("confidence")
        decision_confidence_raw = payload.get("decision_confidence")

        if confidence_raw is not None and not isinstance(confidence_raw, Mapping):
            raise ValueError("confidence 必须是对象")
        if decision_confidence_raw is not None and not isinstance(decision_confidence_raw, Mapping):
            raise ValueError("decision_confidence 必须是对象")

        if decision_confidence_raw is not None:
            confidence = DecisionConfidence.from_dict(decision_confidence_raw)
            if confidence_raw is not None:
                legacy_conf = DecisionConfidence.from_dict(confidence_raw)
                if legacy_conf.level != confidence.level or abs(float(legacy_conf.score) - float(confidence.score)) > 1e-9:
                    raise ValueError("confidence 与 decision_confidence 不一致")
        else:
            confidence_payload = confidence_raw or {}
            if not isinstance(confidence_payload, Mapping):
                raise ValueError("confidence/decision_confidence 必须是对象")
            confidence = DecisionConfidence.from_dict(confidence_payload)

        cross_horizon_policy = payload.get("cross_horizon_policy") or {}
        if not isinstance(cross_horizon_policy, dict):
            raise ValueError("cross_horizon_policy 必须是对象")
        risk_hints = payload.get("risk_hints") or {}
        if not isinstance(risk_hints, dict):
            raise ValueError("risk_hints 必须是对象")

        trace_id_raw = payload.get("trace_id")
        trace_id = None if trace_id_raw is None else str(trace_id_raw).strip() or None
        return cls(
            decision_id=decision_id,
            exchange=exchange,
            account_id=account_id,
            symbol=symbol,
            direction_intent=direction,  # type: ignore[arg-type]
            confidence=confidence,
            cross_horizon_policy=cross_horizon_policy,
            risk_hints=risk_hints,
            trace_id=trace_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "decision_id": self.decision_id,
            "exchange": self.exchange,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "direction_intent": self.direction_intent,
            "confidence": self.confidence.to_dict(),
            "decision_confidence": self.confidence.to_dict(),
            "cross_horizon_policy": self.cross_horizon_policy,
            "risk_hints": self.risk_hints,
        }
        if self.trace_id:
            data["trace_id"] = self.trace_id
        return data


@dataclass(frozen=True)
class ExecutionResult:
    """execution 对外输出契约（v1）。"""

    decision_id: str
    execution_action: ExecutionAction
    reject_reason: Optional[str]
    applied_risk_rules: List[str]
    order_result: Optional[Dict[str, Any]] = None
    signal_result: Optional[Dict[str, Any]] = None
    policy_snapshot: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExecutionResult":
        decision_id = str(payload.get("decision_id", "")).strip()
        action = str(payload.get("execution_action", "")).strip().lower()
        reject_reason_raw = payload.get("reject_reason")
        applied_rules_raw = payload.get("applied_risk_rules") or []
        order_result_raw = payload.get("order_result")
        signal_result_raw = payload.get("signal_result")
        policy_snapshot_raw = payload.get("policy_snapshot")
        notes_raw = payload.get("notes")

        if not decision_id:
            raise ValueError("decision_id 不能为空")
        if action not in {"add", "reduce", "hold", "exit", "skip"}:
            raise ValueError("execution_action 必须是 add/reduce/hold/exit/skip")
        if not isinstance(applied_rules_raw, list):
            raise ValueError("applied_risk_rules 必须是字符串数组")
        applied_rules = [str(item).strip() for item in applied_rules_raw if str(item).strip()]
        if reject_reason_raw is not None and not str(reject_reason_raw).strip():
            raise ValueError("reject_reason 非空时必须是非空字符串")
        reject_reason = None if reject_reason_raw is None else str(reject_reason_raw).strip()
        if order_result_raw is not None and not isinstance(order_result_raw, dict):
            raise ValueError("order_result 必须是对象")
        order_result = None if order_result_raw is None else dict(order_result_raw)
        if signal_result_raw is not None and not isinstance(signal_result_raw, dict):
            raise ValueError("signal_result 必须是对象")
        signal_result = None if signal_result_raw is None else dict(signal_result_raw)
        if policy_snapshot_raw is not None and not isinstance(policy_snapshot_raw, dict):
            raise ValueError("policy_snapshot 必须是对象")
        policy_snapshot: Optional[Dict[str, Any]] = None
        if isinstance(policy_snapshot_raw, dict):
            policy_version = str(policy_snapshot_raw.get("policy_version") or "").strip()
            ruleset_hash = str(policy_snapshot_raw.get("ruleset_hash") or "").strip()
            if not policy_version or not ruleset_hash:
                raise ValueError("policy_snapshot.policy_version/ruleset_hash 不能为空")
            policy_snapshot = {
                "policy_version": policy_version,
                "ruleset_hash": ruleset_hash,
            }
        notes = None if notes_raw is None else str(notes_raw).strip() or None
        return cls(
            decision_id=decision_id,
            execution_action=action,  # type: ignore[arg-type]
            reject_reason=reject_reason,
            applied_risk_rules=applied_rules,
            order_result=order_result,
            signal_result=signal_result,
            policy_snapshot=policy_snapshot,
            notes=notes,
        )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "decision_id": self.decision_id,
            "execution_action": self.execution_action,
            "reject_reason": self.reject_reason,
            "applied_risk_rules": self.applied_risk_rules,
        }
        if self.order_result is not None:
            data["order_result"] = self.order_result
        if self.signal_result is not None:
            data["signal_result"] = self.signal_result
        if self.policy_snapshot is not None:
            data["policy_snapshot"] = self.policy_snapshot
        if self.notes:
            data["notes"] = self.notes
        return data
