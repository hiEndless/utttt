from __future__ import annotations

import time
from typing import Any, Dict

from services.agent_server_new.ports.memory.symbol_memory_maintenance import SymbolMemoryMaintenance


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


async def run_symbol_memory_summary_once(
    *,
    maintenance: SymbolMemoryMaintenance,
    limit_symbols: int = 1000,
    summary_window: int = 50,
    top_risk_n: int = 5,
) -> Dict[str, Any]:
    started_ms = int(time.time() * 1000)
    symbols = await maintenance.list_symbols(limit=max(1, int(limit_symbols)))
    total = len(symbols)
    success = 0
    failed = 0
    last_error = ""
    candidates = []

    for item in symbols:
        exchange = str((item or {}).get("exchange") or "").strip()
        symbol = str((item or {}).get("symbol") or "").strip()
        if not exchange or not symbol:
            failed += 1
            continue
        try:
            summary = await maintenance.rebuild_symbol_summary(
                exchange=exchange,
                symbol=symbol,
                window=max(1, int(summary_window)),
            )
            success += 1
            summary_obj = dict(summary or {})
            candidates.append(
                {
                    "exchange": exchange,
                    "symbol": symbol,
                    "contract_warning_count": _to_int(summary_obj.get("contract_warning_count"), 0),
                    "event_count": _to_int(summary_obj.get("event_count"), 0),
                    "last_decision_ts": _to_int(summary_obj.get("last_decision_ts"), 0),
                    "recent_contract_warning_types": [
                        str(x) for x in list(summary_obj.get("recent_contract_warning_types") or []) if str(x or "").strip()
                    ][:5],
                }
            )
        except Exception as exc:  # pragma: no cover
            failed += 1
            last_error = str(exc)

    high_risk_symbols = sorted(
        candidates,
        key=lambda x: (
            -_to_int(x.get("contract_warning_count"), 0),
            -_to_int(x.get("event_count"), 0),
            -_to_int(x.get("last_decision_ts"), 0),
        ),
    )[: max(1, int(top_risk_n))]

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
        "high_risk_symbols": high_risk_symbols,
    }
