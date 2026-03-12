from __future__ import annotations

import time
from typing import Any, Dict, List

from services.agent_server_new.domain.symbol_memory_summary import build_symbol_memory_summary


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


class InMemorySymbolMemoryAdapter:
    """最小 in-memory 记忆适配器：同时实现 provider + recorder。"""

    def __init__(self, *, max_raw_per_symbol: int = 200) -> None:
        self._max_raw_per_symbol = max(20, int(max_raw_per_symbol))
        self._store: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _key(exchange: str, symbol: str) -> str:
        return f"{str(exchange or '').strip().lower()}:{str(symbol or '').strip().upper()}"

    async def get_symbol_memory(self, exchange: str, symbol: str, limit: int = 20) -> Dict[str, Any]:
        key = self._key(exchange, symbol)
        item = _safe_dict(self._store.get(key))
        raw: List[Dict[str, Any]] = list(item.get("raw") or [])
        lim = max(1, int(limit))
        return {
            "summary": _safe_dict(item.get("summary")),
            "recent": raw[-lim:],
            "ts": int(time.time() * 1000),
        }

    async def record_symbol_memory(self, exchange: str, symbol: str, payload: Dict[str, Any]) -> None:
        key = self._key(exchange, symbol)
        if key not in self._store:
            self._store[key] = {"raw": [], "summary": {}}
        slot = self._store[key]
        raw: List[Dict[str, Any]] = list(slot.get("raw") or [])
        entry = _safe_dict(payload)
        entry_ts = int(entry.get("ts") or time.time() * 1000)
        entry["ts"] = entry_ts
        raw.append(entry)
        if len(raw) > self._max_raw_per_symbol:
            raw = raw[-self._max_raw_per_symbol :]
        slot["raw"] = raw
        slot["summary"] = build_symbol_memory_summary(
            exchange=exchange,
            symbol=symbol,
            raw_records=raw,
            window=self._max_raw_per_symbol,
        )

    async def list_symbols(self, limit: int = 1000) -> List[Dict[str, str]]:
        lim = max(1, int(limit))
        items: List[Dict[str, str]] = []
        for key in list(self._store.keys())[:lim]:
            if ":" not in key:
                continue
            exchange, symbol = key.split(":", 1)
            items.append({"exchange": exchange, "symbol": symbol})
        return items

    async def rebuild_symbol_summary(self, exchange: str, symbol: str, *, window: int = 50) -> Dict[str, Any]:
        key = self._key(exchange, symbol)
        if key not in self._store:
            self._store[key] = {"raw": [], "summary": {}}
        slot = self._store[key]
        raw: List[Dict[str, Any]] = list(slot.get("raw") or [])
        summary = build_symbol_memory_summary(
            exchange=exchange,
            symbol=symbol,
            raw_records=raw,
            window=max(1, int(window)),
        )
        slot["summary"] = summary
        return summary
