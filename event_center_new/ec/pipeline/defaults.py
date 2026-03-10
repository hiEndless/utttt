from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts import (
    ClassifiedEvent,
    Direction,
    Evidence,
    EventContextSnapshot,
    EventEnvelope,
    PrioritizedEvent,
    SelectedEvent,
)
from .stages import EvidenceExtractor, FinalGate, FinalGateInput, L0Processor, L1Aggregator, Normalizer


class PassThroughNormalizer(Normalizer):
    """默认标准化器：当前直接透传。"""

    def normalize(self, event: EventEnvelope) -> EventEnvelope:
        return event


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
            conf_value = None if raw_conf is None else float(raw_conf)
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
                    attrs=dict(raw.get("attrs") or {}),
                )
            )
        return out


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
        return SelectedEvent(
            asset=inp.context.asset,
            ts_ms=inp.context.ts_ms,
            selected_type="event.selected",
            direction_hint=direction_hint,
            priority=priority,  # type: ignore[arg-type]
            context_snapshot=inp.context,
            trigger_event=inp.trigger_event,
            route=route,
        )
