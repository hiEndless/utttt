from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
)


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


def news_card() -> AgentCard:
    skill = AgentSkill(
        id="news_analysis",
        name="Analyze and summarize news context",
        description="Fetch and analyze market or domain news",
        tags=["news", "market", "summary"],
        examples=["Summarize latest market news", "Key headlines for BTC"],
    )
    return _base_card("News Expert", "Professional news analysis agent", skill, url="http://localhost:10002/")


def technical_card() -> AgentCard:
    skill = AgentSkill(
        id="technical_analysis",
        name="Analyze technical indicators and trends",
        description="Perform technical analysis and trend assessment",
        tags=["technical", "indicators", "trend"],
        examples=["Analyze BTC trend", "RSI and MACD summary"],
    )
    return _base_card("Technical Expert", "Technical analysis agent", skill, url="http://localhost:10001/")


def risk_card() -> AgentCard:
    skill = AgentSkill(
        id="risk_assessment",
        name="Assess risk exposure and scenarios",
        description="Risk analysis and scenario evaluation",
        tags=["risk", "exposure", "scenario"],
        examples=["Assess drawdown risk", "Volatility risk overview"],
    )
    return _base_card("Risk Expert", "Risk assessment agent", skill, url="http://localhost:10003/")


def portfolio_card() -> AgentCard:
    skill = AgentSkill(
        id="portfolio_management",
        name="Suggest portfolio adjustments",
        description="Propose position sizing and adjustments",
        tags=["portfolio", "allocation", "position"],
        examples=["Adjust BTCUSDT position", "Rebalance suggestions"],
    )
    return _base_card("Portfolio Expert", "Portfolio management agent", skill, url="http://localhost:10004/")


def get_agent_card(name: str) -> AgentCard:
    if name == "news":
        return news_card()
    if name == "technical":
        return technical_card()
    if name == "risk":
        return risk_card()
    if name == "portfolio":
        return portfolio_card()
    return technical_card()