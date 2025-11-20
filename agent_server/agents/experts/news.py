from typing import Any


class NewsExpert:
    name = "news"

    async def run(self, query: str) -> str:
        from agno.agent import Agent
        from agno.models.openai import OpenAIChat

        agent = Agent(model=OpenAIChat(id="gpt-4o-mini"), instructions="Summarize market-related news context")
        resp = await agent.arun(query)
        return str(resp.content)