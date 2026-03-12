from __future__ import annotations

import time
from typing import Any, Dict

from agent_server_new.ports.memory.symbol_memory_maintenance import SymbolMemoryMaintenance


async def run_symbol_memory_summary_once(
    *,
    maintenance: SymbolMemoryMaintenance,
    limit_symbols: int = 1000,
    summary_window: int = 50,
) -> Dict[str, Any]:
    started_ms = int(time.time() * 1000)
    symbols = await maintenance.list_symbols(limit=max(1, int(limit_symbols)))
    total = len(symbols)
    success = 0
    failed = 0
    last_error = ""

    for item in symbols:
        exchange = str((item or {}).get("exchange") or "").strip()
        symbol = str((item or {}).get("symbol") or "").strip()
        if not exchange or not symbol:
            failed += 1
            continue
        try:
            await maintenance.rebuild_symbol_summary(
                exchange=exchange,
                symbol=symbol,
                window=max(1, int(summary_window)),
            )
            success += 1
        except Exception as exc:  # pragma: no cover
            failed += 1
            last_error = str(exc)

    ended_ms = int(time.time() * 1000)
    return {
        "ok": failed == 0,
        "total_symbols": total,
        "success_symbols": success,
        "failed_symbols": failed,
        "summary_window": max(1, int(summary_window)),
        "started_ms": started_ms,
        "ended_ms": ended_ms,
        "duration_ms": max(0, ended_ms - started_ms),
        "last_error": last_error,
    }
