from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Mapping

from execution_service.domain.contracts import DecisionIntent


@dataclass
class MockExecutionSink:
    """模拟执行下沉：用于联调阶段回填 order_result。"""

    venue: str = "mock_exchange"

    async def submit(self, decision: DecisionIntent, execution_action: str) -> Dict[str, Any]:
        order_id = f"mock-{uuid.uuid4().hex[:12]}"
        return {
            "submitted": True,
            "venue": self.venue,
            "order_id": order_id,
            "decision_id": decision.decision_id,
            "exchange": decision.exchange,
            "symbol": decision.symbol,
            "direction_intent": decision.direction_intent,
            "execution_action": execution_action,
            "ts": int(time.time() * 1000),
        }

    async def reconcile(self, order_id: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "mode": "mock",
            "venue": self.venue,
            "order_id": str(order_id),
            "decision_id": str(payload.get("decision_id") or "").strip() or None,
            "exchange": str(payload.get("exchange") or "").strip() or None,
            "symbol": str(payload.get("symbol") or "").strip().upper() or None,
            "status": "filled",
            "filled_qty": 1.0,
            "avg_price": 1000.0,
            "ts": int(time.time() * 1000),
        }
