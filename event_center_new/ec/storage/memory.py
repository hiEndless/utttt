from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..contracts import Evidence, EventEnvelope


@dataclass(frozen=True)
class MemoryPut:
    event: EventEnvelope
    evidences: list[Evidence]


class EventMemory(Protocol):
    def put(self, item: MemoryPut) -> None:
        ...

    def get_active_evidences(self, asset: str, ts_ms: int) -> list[Evidence]:
        ...


@dataclass(frozen=True)
class _StoredEvidence:
    evidence: Evidence
    expire_at_ms: int


class InMemoryEventMemory:
    """基于 TTL 的内存事件记忆实现。"""

    def __init__(self) -> None:
        self._items: dict[str, list[_StoredEvidence]] = {}

    def put(self, item: MemoryPut) -> None:
        asset = str(item.event.asset or "").strip()
        if not asset:
            return
        curr = self._items.setdefault(asset, [])
        for ev in item.evidences:
            expire_at = int(ev.ts_ms) + max(0, int(ev.ttl_ms))
            curr.append(_StoredEvidence(evidence=ev, expire_at_ms=expire_at))
        # 中文注释：每次写入后顺手裁剪过期项，避免内存膨胀。
        self._items[asset] = [x for x in curr if x.expire_at_ms > int(item.event.ts_ms)]

    def get_active_evidences(self, asset: str, ts_ms: int) -> list[Evidence]:
        key = str(asset or "").strip()
        curr = self._items.get(key, [])
        active = [x for x in curr if x.expire_at_ms > int(ts_ms)]
        self._items[key] = active
        return [x.evidence for x in active]


class InMemoryLayerStore:
    """最小分层落盘内存实现：raw/normalized/evidence/context/selected。"""

    def __init__(self) -> None:
        self.raw: list[dict[str, Any]] = []
        self.normalized: list[dict[str, Any]] = []
        self.evidence: list[dict[str, Any]] = []
        self.context: list[dict[str, Any]] = []
        self.selected: list[dict[str, Any]] = []

    def write_raw(self, payload: dict[str, Any]) -> None:
        self.raw.append(dict(payload))

    def write_normalized(self, payload: dict[str, Any]) -> None:
        self.normalized.append(dict(payload))

    def write_evidence(self, payload: dict[str, Any]) -> None:
        self.evidence.append(dict(payload))

    def write_context(self, payload: dict[str, Any]) -> None:
        self.context.append(dict(payload))

    def write_selected(self, payload: dict[str, Any]) -> None:
        self.selected.append(dict(payload))
