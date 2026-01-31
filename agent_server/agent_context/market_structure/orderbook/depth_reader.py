"""orderbook.depth_reader: 从 WS 写入的 depth:{exchange}:{symbol} 获取最新一帧快照。"""

from __future__ import annotations

import json
from typing import Any, Dict, List


async def read_orderbook_depth(exchange: str, symbol: str, *, client: object) -> Dict[str, Any] | None:
    key = f"depth:{exchange}:{symbol}"
    try:
        ktype = await client.type(key)
    except Exception:
        ktype = None

    if str(ktype) == "stream":
        try:
            res = await client.xrevrange(key, max="+", min="-", count=1)
        except Exception:
            res = None
        if not res:
            return None
        _, fields = res[0]
        payload = fields.get("payload") if isinstance(fields, dict) else None
        if isinstance(payload, str) and payload:
            try:
                return json.loads(payload)
            except Exception:
                return None
        try:
            bids_raw = fields.get("bids") if isinstance(fields, dict) else None
            asks_raw = fields.get("asks") if isinstance(fields, dict) else None
            if isinstance(bids_raw, str) and isinstance(asks_raw, str) and bids_raw and asks_raw:
                return {"bids": json.loads(bids_raw), "asks": json.loads(asks_raw)}
        except Exception:
            return None
        return None

    try:
        raw = await client.get(key)
    except Exception:
        raw = None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _entry_id_ts(entry_id: str) -> int:
    try:
        return int(str(entry_id).split("-")[0])
    except Exception:
        return 0


async def read_orderbook_depth_stream(
    exchange: str,
    symbol: str,
    *,
    client: object,
    count: int = 300,
) -> List[Dict[str, Any]]:
    key = f"depth:{exchange}:{symbol}"
    try:
        ktype = await client.type(key)
    except Exception:
        ktype = None

    if str(ktype) != "stream":
        latest = await read_orderbook_depth(exchange, symbol, client=client)
        return [{"ts": 0, "depth": latest}] if isinstance(latest, dict) else []

    try:
        res = await client.xrevrange(key, max="+", min="-", count=max(1, int(count)))
    except Exception:
        res = None
    if not res:
        return []

    out: List[Dict[str, Any]] = []
    for entry_id, fields in reversed(res):
        if not isinstance(fields, dict):
            continue
        payload = fields.get("payload")
        ts = fields.get("ts")
        ts_ms = 0
        try:
            ts_ms = int(ts) if ts is not None else 0
        except Exception:
            ts_ms = 0
        if ts_ms <= 0:
            ts_ms = _entry_id_ts(str(entry_id))

        depth = None
        if isinstance(payload, str) and payload:
            try:
                depth = json.loads(payload)
            except Exception:
                depth = None
        if not isinstance(depth, dict):
            try:
                bids_raw = fields.get("bids")
                asks_raw = fields.get("asks")
                if isinstance(bids_raw, str) and isinstance(asks_raw, str) and bids_raw and asks_raw:
                    depth = {"bids": json.loads(bids_raw), "asks": json.loads(asks_raw)}
            except Exception:
                depth = None

        if isinstance(depth, dict):
            out.append({"ts": int(ts_ms), "depth": depth})

    return out
