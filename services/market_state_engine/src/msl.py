from __future__ import annotations

from typing import Any, Dict

from services.market_state_engine.src.contracts import MarketStateMSL


def build_msl_from_market_structure(exchange: str, symbol: str, market_structure: Dict[str, Any]) -> MarketStateMSL:
    """兼容入口：基于 MarketStateEngine 生成 MSL。"""

    from services.market_state_engine.src.engine import MarketStateEngine

    engine = MarketStateEngine()
    msl, _ = engine.build(exchange=exchange, symbol=symbol, market_structure=market_structure)
    return msl
