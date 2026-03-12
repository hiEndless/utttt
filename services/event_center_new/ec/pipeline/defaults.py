from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts import (
    ClassifiedEvent,
    Direction,
    Evidence,
    EventContextSnapshot,
    EventEnvelope,
    EventTrace,
    PrioritizedEvent,
    SelectedEvent,
)
from .stages import EvidenceExtractor, FinalGate, FinalGateInput, L0Processor, L1Aggregator, Normalizer


class PassThroughNormalizer(Normalizer):
    """默认标准化器：当前直接透传。"""

    def normalize(self, event: EventEnvelope) -> EventEnvelope:
        payload = dict(event.payload or {})
        evidences = payload.get("evidences")
        if not isinstance(evidences, list):
            return event
        normalized_evidences: list[dict[str, Any]] = []
        for raw in evidences:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            raw_attrs = dict(item.get("attrs") or {}) if isinstance(item.get("attrs"), dict) else {}
            attrs = _normalize_evidence_attrs(item.get("attrs"))
            if attrs:
                item["attrs"] = attrs
            elif "attrs" in item:
                item.pop("attrs", None)
            raw_conf = item.get("evidence_confidence")
            if raw_conf is None:
                raw_conf = item.get("confidence")
            if raw_conf is None:
                raw_conf = raw_attrs.get("confidence")
            conf = _coerce_float(raw_conf)
            if conf is not None:
                item["evidence_confidence"] = conf
                item["confidence"] = conf
            normalized_evidences.append(item)
        payload["evidences"] = normalized_evidences
        return EventEnvelope(
            id=event.id,
            ts_ms=event.ts_ms,
            asset=event.asset,
            kind=event.kind,
            type=event.type,
            source=event.source,
            importance=event.importance,
            ttl_ms=event.ttl_ms,
            payload=payload,
            exchange=event.exchange,
            account_id=event.account_id,
            meta=dict(event.meta or {}),
            trace=event.trace,
        )


class PayloadEvidenceExtractor(EvidenceExtractor):
    """从 event.payload['evidences'] 中提取证据。"""

    def extract(self, event: EventEnvelope) -> list[Evidence]:
        payload = dict(event.payload or {})
        items = payload.get("evidences")
        if not isinstance(items, list):
            return []
        out: list[Evidence] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            direction = str(raw.get("direction") or "neutral").strip().lower()
            if direction not in {"bullish", "bearish", "neutral", "mixed"}:
                direction = "neutral"
            horizon = str(raw.get("horizon") or "short").strip().lower()
            if horizon not in {"short", "mid", "long"}:
                horizon = "short"
            source_refs = raw.get("source_refs")
            raw_conf = raw.get("evidence_confidence")
            if raw_conf is None:
                raw_conf = raw.get("confidence")
            if raw_conf is None:
                raw_conf = dict(raw.get("attrs") or {}).get("confidence")
            conf_value = _coerce_float(raw_conf)
            out.append(
                Evidence(
                    ts_ms=int(raw.get("ts_ms") or event.ts_ms),
                    type=str(raw.get("type") or event.type),
                    direction=direction,  # type: ignore[arg-type]
                    strength=float(raw.get("strength") or 0.0),
                    horizon=horizon,  # type: ignore[arg-type]
                    ttl_ms=int(raw.get("ttl_ms") or event.ttl_ms),
                    importance=float(raw.get("importance") or event.importance),
                    evidence_confidence=conf_value,
                    confidence=conf_value,
                    source_refs=list(source_refs) if isinstance(source_refs, list) else [],
                    attrs=_normalize_evidence_attrs(raw.get("attrs")),
                )
            )
        return out


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return None


def _normalize_evidence_attrs(payload: Any) -> dict[str, Any]:
    attrs = dict(payload or {}) if isinstance(payload, dict) else {}
    # 中文注释：歧义字段在事件层统一收敛，避免下游把 market_state/risk_bias 误读为全局语义对象。
    if "market_state" in attrs:
        attrs.setdefault("source_market_state", attrs.get("market_state"))
        attrs.pop("market_state", None)
    if "risk_bias" in attrs:
        attrs.setdefault("action_risk_bias", attrs.get("risk_bias"))
        attrs.pop("risk_bias", None)
    semantic_scope = dict(attrs.get("semantic_scope") or {}) if isinstance(attrs.get("semantic_scope"), dict) else {}
    semantic_scope.setdefault("confidence", "evidence_confidence")
    if "source_market_state" in attrs:
        semantic_scope.setdefault("source_market_state", "upstream_local_state")
    if "action_risk_bias" in attrs:
        semantic_scope.setdefault("action_risk_bias", "action_level_bias")
    if semantic_scope:
        attrs["semantic_scope"] = semantic_scope
    attrs.pop("confidence", None)
    return attrs


class HeuristicL0Processor(L0Processor):
    """最小 L0：按证据分数得到方向确认。"""

    def process(self, context: EventContextSnapshot) -> ClassifiedEvent:
        bull = 0.0
        bear = 0.0
        for ev in context.key_evidences:
            conf = 1.0 if ev.confidence is None else max(0.0, min(1.0, ev.confidence))
            score = max(0.0, ev.strength) * max(0.0, ev.importance) * conf
            if ev.direction == "bullish":
                bull += score
            elif ev.direction == "bearish":
                bear += score
            elif ev.direction == "mixed":
                bull += score * 0.5
                bear += score * 0.5
        total = bull + bear
        diff = bull - bear
        direction: Direction
        if total <= 0:
            direction = "neutral"
        elif abs(diff) <= max(0.05, total * 0.15):
            direction = "mixed"
        else:
            direction = "bullish" if diff > 0 else "bearish"
        confidence = 0.0 if total <= 0 else min(1.0, abs(diff) / total)
        priority = "high" if total >= 1.2 else "medium" if total >= 0.5 else "low"
        return ClassifiedEvent(
            asset=context.asset,
            ts_ms=context.ts_ms,
            confirmed_direction=direction,
            score=round(total, 6),
            confidence=round(confidence, 6),
            classification_confidence=round(confidence, 6),
            priority=priority,  # type: ignore[arg-type]
            window={"evidence_count": len(context.key_evidences)},
            reasons=[],
        )


class HeuristicL1Aggregator(L1Aggregator):
    """最小 L1：封装优先级和可解释分数。"""

    def aggregate(self, context: EventContextSnapshot, l0: ClassifiedEvent | None) -> PrioritizedEvent:
        l0_priority = "low" if l0 is None else l0.priority
        classification = "conflict" if (l0 and l0.confirmed_direction == "mixed") else "directional"
        component_scores = {
            "l0_score": 0.0 if l0 is None else l0.score,
            "l0_confidence": 0.0 if l0 is None else l0.confidence,
            "classification_confidence": 0.0 if l0 is None else l0.classification_confidence,
            "conflict_count": len(context.conflicts),
        }
        return PrioritizedEvent(
            asset=context.asset,
            ts_ms=context.ts_ms,
            classification=classification,
            component_scores=component_scores,
            key_evidences=list(context.key_evidences),
            conflicts=list(context.conflicts),
            routing_hints={},
            priority=l0_priority,  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class SelectPolicyConfig:
    mixed_min_score: float = 0.25
    mixed_min_evidences: int = 2
    mixed_output_priority: str = "low"


class DeterministicFinalGate(FinalGate):
    """最小 select gate，内置 mixed 降权与噪声过滤策略。"""

    def __init__(self, cfg: SelectPolicyConfig | None = None) -> None:
        self._cfg = cfg or SelectPolicyConfig()

    def emit(self, inp: FinalGateInput) -> SelectedEvent | None:
        if inp.l0 is None or inp.l1 is None:
            return None
        direction_hint = inp.l0.confirmed_direction
        priority = inp.l1.priority
        route: dict[str, Any] = {
            "to_market_state_engine": True,
            "to_agent_server_new": True,
            "review_required": False,
        }
        if direction_hint == "mixed":
            if inp.l0.score < self._cfg.mixed_min_score or len(inp.context.key_evidences) < self._cfg.mixed_min_evidences:
                return None
            priority = self._cfg.mixed_output_priority  # type: ignore[assignment]
            route["review_required"] = True
            route["to_agent_server_new"] = False
            route["mixed_policy"] = "degrade_and_route_state_only"
        trace = EventTrace(schema_version="selected-v2", produced_by="event_center_new")
        if inp.trigger_event is not None and inp.trigger_event.trace is not None:
            trace_raw = inp.trigger_event.trace
            trace = EventTrace(
                dedup_key=trace_raw.dedup_key,
                correlation_id=trace_raw.correlation_id,
                parent_id=trace_raw.parent_id,
                produced_by=trace_raw.produced_by or "event_center_new",
                schema_version=trace_raw.schema_version or "selected-v2",
            )
        return SelectedEvent(
            asset=inp.context.asset,
            ts_ms=inp.context.ts_ms,
            selected_type="event.selected",
            direction_hint=direction_hint,
            priority=priority,  # type: ignore[arg-type]
            context_snapshot=inp.context,
            trigger_event=inp.trigger_event,
            source=None if inp.trigger_event is None else inp.trigger_event.source,
            trace=trace,
            route=route,
            event_ts_ms=(
                int(inp.trigger_event.ts_ms)
                if inp.trigger_event is not None
                else int(inp.context.ts_ms)
            ),
            processed_ts_ms=int(inp.context.ts_ms),
        )
