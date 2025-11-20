from typing import Any

from .news import NewsExpert
from .technical import TechnicalExpert
from .risk import RiskExpert
from .portfolio import PortfolioExpert
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
    return TechnicalExpert()


def load_card(name: str):
    return get_agent_card(name)
