class TechnicalExpert:
    name = "technical"

    async def run(self, query: str) -> str:
        from agno.agent import Agent
        from agno.models.openai import OpenAIChat

        agent = Agent(model=OpenAIChat(id="gpt-4o-mini"), instructions="Analyze technical indicators and trend context")
        resp = await agent.arun(query)
        return str(resp.content)