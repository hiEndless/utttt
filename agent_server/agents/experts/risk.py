class RiskExpert:
    name = "risk"

    async def run(self, query: str) -> str:
        from agno.agent import Agent
        from agno.models.openai import OpenAIChat

        agent = Agent(model=OpenAIChat(id="gpt-4o-mini"), instructions="Assess risk exposure and scenario impacts")
        resp = await agent.arun(query)
        return str(resp.content)