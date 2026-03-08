from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class FeatureSnapshot:
    exchange: str
    symbol: str
    indicators: Dict[str, Any] = field(default_factory=dict)
    derived_metrics: Dict[str, Any] = field(default_factory=dict)
    structure_snapshot: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawStructureSnapshot:
    exchange: str
    symbol: str
    raw_market_structure: Dict[str, Any] = field(default_factory=dict)
