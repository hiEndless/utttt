import json
from typing import Any, Dict, Optional
import uuid


def build_event_id(*args):
    if len(args) == 3:
        symbol, event_type, ts_ms = args
        return f"{symbol}.{event_type}.{ts_ms}"
    if len(args) == 5:
        exchange, account_id, symbol, event_type, ts_ms = args
        return f"{exchange}.{account_id}.{symbol}.{event_type}.{ts_ms}"
    try:
        return ".".join(str(a) for a in args)
    except Exception:
        return ""


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
    event_id = build_event_id(exchange, account_id, symbol, event_type, timestamp_ms)
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
        "event_level": int(event_level),
        "payload": json.dumps(payload, ensure_ascii=False),
        "meta": json.dumps(meta, ensure_ascii=False),
    }
    return raw
