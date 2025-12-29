from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class IndicatorSnapshot:
    tf: str
    name: str
    fields: Dict[str, Any]
    prev: Optional[Dict[str, Any]] = None
