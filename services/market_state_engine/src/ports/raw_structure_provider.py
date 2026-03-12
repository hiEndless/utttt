from __future__ import annotations

from typing import Any, Dict, Protocol


class RawStructureProvider(Protocol):
    """原始结构提供端口：状态层只依赖该抽象读取 market_structure。"""

    async def get_raw_structure(self, exchange: str, symbol: str) -> Dict[str, Any]:
        """返回指定交易所和交易对的原始市场结构。"""
