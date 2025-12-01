import json
from typing import Any, Dict, Optional
import uuid

def build_event_id(symbol, event_type, ts_ms):
    return f"{symbol}.{event_type}.{ts_ms}"


def build_raw_event(
    *,
    exchange: str,
    symbol: str,
    account_id: str,
    source: str,
    event_class: str,
    event_type: str,
    event_level: int,
    timestamp_ms: int,
    payload: Dict[str, Any],
    meta_version: str = "1.0",
    trace_id: Optional[str] = None,
    latency_ms: Optional[int] = None,
) -> Dict[str, str]:
    event_id = build_event_id(symbol, event_type, timestamp_ms)
    meta = {
        "version": meta_version,
        "trace_id": trace_id or uuid.uuid4().hex,
        "latency_ms": latency_ms or 0,
        "producer": source,
    }
    raw = {
        "event_id": event_id,
        "timestamp": str(timestamp_ms),
        "source": source,
        "exchange": exchange,
        "symbol": symbol,
        "account_id": account_id,
        "event_class": event_class,
        "event_type": event_type,
        "event_level": str(event_level),
        "payload": json.dumps(payload, ensure_ascii=False),
        "meta": json.dumps(meta, ensure_ascii=False),
    }
    return raw