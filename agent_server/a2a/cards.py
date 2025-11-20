from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
)
from agent_server.configs.source import get_agent_config


def get_agent_card(name: str) -> AgentCard:
    if name == "news":
        return news_card()
    if name == "technical":
        return technical_card()
    if name == "risk":
        return risk_card()
    if name == "portfolio":
        return portfolio_card()
    if name == "reflection":
        return reflection_card()
    if name == "fusion":
        return fusion_card()
    return technical_card()


def _base_card(name: str, description: str, skill: AgentSkill, url: str) -> AgentCard:
    return AgentCard(
        name=name,
        description=description,
        url=url,
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        authentication={"schemes": ["public"]},
        skills=[skill],
    )


def _load_agent_url(name: str, default_url: str) -> str:
    cfg = get_agent_config(name)
    url = cfg.get("a2a_url")
    return url or default_url


def news_card() -> AgentCard:
    skill = AgentSkill(
        id="news_analysis",
        name="Analyze and summarize news context",
        description="Fetch and analyze market or domain news",
        tags=["news", "market", "summary"],
        examples=["Summarize latest market news", "Key headlines for BTC"],
    )
    return _base_card("News Expert", "Professional news analysis agent", skill, url=_load_agent_url("news", "http://localhost:10002/"))


def technical_card() -> AgentCard:
    skill = AgentSkill(
        id="technical_analysis",
        name="Analyze technical indicators and trends",
        description="Perform technical analysis and trend assessment",
        tags=["technical", "indicators", "trend"],
        examples=["Analyze BTC trend", "RSI and MACD summary"],
    )
    return _base_card("Technical Expert", "Technical analysis agent", skill, url=_load_agent_url("technical", "http://localhost:10001/"))


def risk_card() -> AgentCard:
    skill = AgentSkill(
        id="risk_assessment",
        name="Assess risk exposure and scenarios",
        description="Risk analysis and scenario evaluation",
        tags=["risk", "exposure", "scenario"],
        examples=["Assess drawdown risk", "Volatility risk overview"],
    )
    return _base_card("Risk Expert", "Risk assessment agent", skill, url=_load_agent_url("risk", "http://localhost:10003/"))


def portfolio_card() -> AgentCard:
    skill = AgentSkill(
        id="portfolio_management",
        name="Suggest portfolio adjustments",
        description="Propose position sizing and adjustments",
        tags=["portfolio", "allocation", "position"],
        examples=["Adjust BTCUSDT position", "Rebalance suggestions"],
    )
    return _base_card("Portfolio Expert", "Portfolio management agent", skill, url=_load_agent_url("portfolio", "http://localhost:10004/"))


def reflection_card() -> AgentCard:
    skill = AgentSkill(
        id="reflection_round",
        name="Reflect and critique outputs",
        description="Critique multi-agent outputs and derive reflection scores",
        tags=["reflection", "critique", "scoring"],
        examples=["Reflect on outputs", "Assign reflection scores"],
    )
    return _base_card("Reflection Agent", "Reflection agent", skill, url=_load_agent_url("reflection", "http://localhost:10005/"))


def fusion_card() -> AgentCard:
    skill = AgentSkill(
        id="fusion_round",
        name="Fuse outputs with weights",
        description="Weighted fusion using base weights and reflection/autoscores",
        tags=["fusion", "weights", "combine"],
        examples=["Fuse outputs", "Produce weighted result"],
    )
    return _base_card("Fusion Agent", "Fusion agent", skill, url=_load_agent_url("fusion", "http://localhost:10006/"))