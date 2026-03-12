from __future__ import annotations

import time
from typing import Any, Dict

from services.agent_server_new.ports.memory.symbol_memory_maintenance import SymbolMemoryMaintenance


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _risk_score(*, now_ms: int, warning_count: int, event_count: int, last_decision_ts: int) -> float:
    if warning_count <= 0:
        return 0.0
    age_ms = max(0, int(now_ms) - max(0, int(last_decision_ts)))
    half_life_ms = 6 * 60 * 60 * 1000
    recency_weight = 1.0 / (1.0 + (float(age_ms) / float(half_life_ms)))
    score = float(warning_count) * 100.0 * recency_weight + min(max(int(event_count), 0), 100) * 0.1
    return round(float(score), 6)


async def run_symbol_memory_summary_once(
    *,
    maintenance: SymbolMemoryMaintenance,
    limit_symbols: int = 1000,
    summary_window: int = 50,
    top_risk_n: int = 5,
    risk_warning_min: int = 1,
    only_risked: bool = True,
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
            warning_count = _to_int(summary_obj.get("contract_warning_count"), 0)
            event_count = _to_int(summary_obj.get("event_count"), 0)
            last_decision_ts = _to_int(summary_obj.get("last_decision_ts"), 0)
            candidates.append(
                {
                    "exchange": exchange,
                    "symbol": symbol,
                    "contract_warning_count": warning_count,
                    "event_count": event_count,
                    "last_decision_ts": last_decision_ts,
                    "risk_score": _risk_score(
                        now_ms=started_ms,
                        warning_count=warning_count,
                        event_count=event_count,
                        last_decision_ts=last_decision_ts,
                    ),
                    "recent_contract_warning_types": [
                        str(x) for x in list(summary_obj.get("recent_contract_warning_types") or []) if str(x or "").strip()
                    ][:5],
                }
            )
        except Exception as exc:  # pragma: no cover
            failed += 1
            last_error = str(exc)

    filtered_candidates = []
    min_warning = max(0, int(risk_warning_min))
    for item in candidates:
        warning_count = _to_int(item.get("contract_warning_count"), 0)
        if bool(only_risked) and warning_count <= 0:
            continue
        if warning_count < min_warning:
            continue
        filtered_candidates.append(item)

    high_risk_symbols = sorted(
        filtered_candidates,
        key=lambda x: (
            -float(x.get("risk_score") or 0.0),
            -_to_int(x.get("contract_warning_count"), 0),
            -_to_int(x.get("event_count"), 0),
            -_to_int(x.get("last_decision_ts"), 0),
        ),
    )[: max(1, int(top_risk_n))]

    ended_ms = int(time.time() * 1000)
    return {
        "schema_version": "symbol-memory-summary-run-v1",
        "report_type": "symbol_memory_summary",
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
        "risk_warning_min": min_warning,
        "only_risked": bool(only_risked),
    }
