from typing import Any
from agent_server.a2a.cards import get_agent_card
try:
    from .analysis.news import NewsExpert
    from .analysis.technical import TechnicalExpert
    from .analysis.force_stats import ForceStatsExpert
    from .analysis.portfolio import PortfolioExpert
    from .analysis.risk import RiskExpert
    from .analysis.trading_decision import TradingDecisionExpert
    from .orchestration.reflection import ReflectionExpert
    from .orchestration.fusion import FusionExpert
    from .orchestration.memory import MemoryExpert  
except ImportError:
    from agent_server.agents.experts.analysis.news import NewsExpert
    from agent_server.agents.experts.analysis.technical import TechnicalExpert
    from agent_server.agents.experts.analysis.force_stats import ForceStatsExpert
    from agent_server.agents.experts.analysis.portfolio import PortfolioExpert
    from agent_server.agents.experts.analysis.risk import RiskExpert
    from agent_server.agents.experts.analysis.trading_decision import TradingDecisionExpert
    from agent_server.agents.experts.orchestration.reflection import ReflectionExpert
    from agent_server.agents.experts.orchestration.fusion import FusionExpert
    from agent_server.agents.experts.orchestration.memory import MemoryExpert  


def load_expert(name: str) -> Any:
    if name == "news":
        return NewsExpert()
    if name == "technical":
        return TechnicalExpert()
    if name == "risk":
        return RiskExpert()
    if name == "portfolio":
        return PortfolioExpert()
    if name == "trading_decision":
        return TradingDecisionExpert()
    if name == "reflection":
        return ReflectionExpert()
    if name == "fusion":
        return FusionExpert()
    if name == "memory":
        return MemoryExpert()
    return TechnicalExpert()


def load_card(name: str):
    return get_agent_card(name)