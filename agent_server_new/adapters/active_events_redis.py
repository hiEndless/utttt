from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agent_server_new.ports.data.active_events_provider import ActiveEventsProvider


@dataclass(frozen=True)
class RedisActiveEventsConfig:
    redis_url: str = "redis://127.0.0.1:6379/0"
    stream: str = "ec:selected"
    limit_default: int = 20
    scan_factor: int = 5

    @classmethod
    def from_env(cls) -> "RedisActiveEventsConfig":
        redis_url = str(os.getenv("AGENT_ACTIVE_EVENTS_REDIS_URL", "redis://127.0.0.1:6379/0") or "redis://127.0.0.1:6379/0").strip()
        stream = str(os.getenv("AGENT_ACTIVE_EVENTS_STREAM", "ec:selected") or "ec:selected").strip()
        try:
            limit_default = max(1, int(str(os.getenv("AGENT_ACTIVE_EVENTS_LIMIT_DEFAULT", "20") or "20").strip()))
        except Exception:
            limit_default = 20
        try:
            scan_factor = max(1, int(str(os.getenv("AGENT_ACTIVE_EVENTS_SCAN_FACTOR", "5") or "5").strip()))
        except Exception:
            scan_factor = 5
        return cls(
            redis_url=redis_url,
            stream=stream or "ec:selected",
            limit_default=limit_default,
            scan_factor=scan_factor,
        )


class RedisActiveEventsProvider(ActiveEventsProvider):
    """从 Redis stream 读取事件中心输出的 active events。"""

    def __init__(self, *, client: Any, cfg: Optional[RedisActiveEventsConfig] = None) -> None:
        self._client = client
        self._cfg = cfg or RedisActiveEventsConfig()

    @classmethod
    def from_env(cls) -> "RedisActiveEventsProvider":
        cfg = RedisActiveEventsConfig.from_env()
        return cls.from_url(cfg.redis_url, cfg=cfg)

    @classmethod
    def from_url(cls, url: str, *, cfg: Optional[RedisActiveEventsConfig] = None) -> "RedisActiveEventsProvider":
        try:
            import redis  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("未安装 redis 依赖，无法启用 RedisActiveEventsProvider") from exc
        client = redis.Redis.from_url(url, decode_responses=True)
        return cls(client=client, cfg=cfg)

    async def get_active_events(self, exchange: str, symbol: str) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._read_events, exchange, symbol)

    def _read_events(self, exchange: str, symbol: str) -> List[Dict[str, Any]]:
        target_limit = max(1, int(self._cfg.limit_default))
        scan_count = max(target_limit, target_limit * max(1, int(self._cfg.scan_factor)))
        rows = self._client.xrevrange(self._cfg.stream, "+", "-", count=scan_count)

        exchange_norm = str(exchange or "").strip().lower()
        symbol_norm = str(symbol or "").strip().lower()
        matched: List[Dict[str, Any]] = []

        for stream_id, fields in list(rows or []):
            payload_raw = (fields or {}).get("payload")
            if not isinstance(payload_raw, str) or not payload_raw:
                continue
            try:
                payload = json.loads(payload_raw)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue

            normalized = self._normalize_active_event(payload, stream_id=stream_id, exchange=exchange, symbol=symbol)
            if not normalized:
                continue
            asset_norm = str(normalized.get("asset") or "").strip().lower()
            if asset_norm and not self._matches_asset(asset=asset_norm, exchange=exchange_norm, symbol=symbol_norm):
                continue
            matched.append(normalized)
            if len(matched) >= target_limit:
                break
        return matched

    @staticmethod
    def _priority_to_score(priority: str) -> float:
        p = str(priority or "").strip().lower()
        if p == "high":
            return 0.9
        if p == "medium":
            return 0.6
        if p == "low":
            return 0.3
        return 0.5

    @staticmethod
    def _matches_asset(*, asset: str, exchange: str, symbol: str) -> bool:
        normalized = str(asset or "").strip().lower()
        if not normalized:
            return False
        if ":" in normalized:
            ex, sym = normalized.split(":", 1)
            if not sym:
                return False
            return (not exchange or ex == exchange) and sym == symbol
        return normalized == symbol

    @classmethod
    def _normalize_active_event(
        cls,
        payload: Dict[str, Any],
        *,
        stream_id: str,
        exchange: str,
        symbol: str,
    ) -> Dict[str, Any]:
        # 中文注释：消费侧冻结最小字段白名单，避免 selected_event 原始字段漂移扩散到 agent。
        event_type = str(payload.get("selected_type") or payload.get("event_type") or payload.get("type") or "").strip()
        if not event_type:
            return {}
        asset = str(payload.get("asset") or payload.get("symbol_id") or "").strip()
        if not asset:
            asset = f"{str(exchange or '').strip().lower()}:{str(symbol or '').strip().upper()}"
        direction = str(payload.get("direction") or payload.get("direction_hint") or "neutral").strip().lower()
        if direction not in {"bullish", "bearish", "neutral", "mixed"}:
            direction = "neutral"
        score_raw = payload.get("score")
        try:
            score = float(score_raw)
        except Exception:
            score = cls._priority_to_score(str(payload.get("priority") or ""))
        timeframe = str(
            payload.get("timeframe")
            or (payload.get("route") or {}).get("horizon")
            or (payload.get("context_snapshot") or {}).get("horizon")
            or "unknown"
        ).strip()
        evidence = payload.get("evidence")
        if evidence is None:
            evidence = payload.get("context_snapshot")
        evidence_obj = evidence if isinstance(evidence, dict) else {}
        trace_obj = payload.get("trace")
        if isinstance(trace_obj, dict) and "trace" not in evidence_obj:
            evidence_obj = {**evidence_obj, "trace": dict(trace_obj)}
        event_id = str(payload.get("event_id") or payload.get("id") or stream_id).strip() or str(stream_id)
        source = str(payload.get("source") or "event_center_new").strip() or "event_center_new"
        return {
            "event_id": event_id,
            "source": source,
            "type": event_type,
            "asset": asset,
            "direction": direction,
            "score": score,
            "timeframe": timeframe,
            "evidence": evidence_obj,
        }
