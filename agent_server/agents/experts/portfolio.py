class PortfolioExpert:
    name = "portfolio"

    async def run(self, query: str) -> str:
        from agno.agent import Agent
        from agno.models.openai import OpenAIChat

        agent = Agent(model=OpenAIChat(id="gpt-4o-mini"), instructions="Propose position adjustments and portfolio actions")
        resp = await agent.arun(query)
        return str(resp.content)