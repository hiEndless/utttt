from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Mapping

from execution_service.domain.contracts import DecisionIntent


@dataclass
class ExchangeExecutionSink:
    """交易所执行骨架适配器（当前为占位实现，便于联调）。"""

    venue: str = "binance"

    async def submit(self, decision: DecisionIntent, execution_action: str) -> Dict[str, Any]:
        order_id = f"{self.venue}-ord-{uuid.uuid4().hex[:12]}"
        # 中文注释：当前不接真实交易所，仅返回可追踪的占位提交回执。
        return {
            "submitted": True,
            "mode": "exchange_skeleton",
            "venue": self.venue,
            "order_id": order_id,
            "decision_id": decision.decision_id,
            "exchange": decision.exchange,
            "symbol": decision.symbol,
            "execution_action": execution_action,
            "status": "submitted",
            "ts": int(time.time() * 1000),
        }

    async def reconcile(self, order_id: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        decision_id = str(payload.get("decision_id") or "").strip()
        exchange = str(payload.get("exchange") or "").strip()
        symbol = str(payload.get("symbol") or "").strip().upper()
        return {
            "mode": "exchange_skeleton",
            "venue": self.venue,
            "order_id": str(order_id),
            "decision_id": decision_id or None,
            "exchange": exchange or None,
            "symbol": symbol or None,
            "status": "submitted",
            "filled_qty": 0.0,
            "avg_price": None,
            "ts": int(time.time() * 1000),
            "note": "占位回执：请替换为真实交易所查询逻辑",
        }
