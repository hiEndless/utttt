from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict

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
