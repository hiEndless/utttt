from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class EventSignal:
    type: str
    payload: Dict[str, Any]
    strength: str