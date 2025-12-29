from dataclasses import dataclass

@dataclass
class Factor:
    plugin: str
    symbol: str
    tf: str
    direction: str  # bullish/bearish/neutral
    strength: int
    ts: int
