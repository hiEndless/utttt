from typing import Any

from .news import NewsExpert
from .technical import TechnicalExpert
from .risk import RiskExpert
from .portfolio import PortfolioExpert
from .reflection import ReflectionExpert
from .fusion import FusionExpert
from .memory import MemoryExpert
from agent_server.a2a.cards import get_agent_card


def load_expert(name: str) -> Any:
    if name == "news":
        return NewsExpert()
    if name == "technical":
        return TechnicalExpert()
    if name == "risk":
        return RiskExpert()
    if name == "portfolio":
        return PortfolioExpert()
    if name == "reflection":
        return ReflectionExpert()
    if name == "fusion":
        return FusionExpert()
    if name == "memory":
        return MemoryExpert()
    return TechnicalExpert()


def load_card(name: str):
    return get_agent_card(name)