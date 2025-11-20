from typing import Any


class NewsExpert:
    name = "news"

    async def run(self, query: str) -> str:
        from agno.agent import Agent
        from agno.models.openai import OpenAIChat
        from agent_server.configs.source import get_agent_config

        cfg = get_agent_config(self.name)

        model_id = cfg.get("model_id", "gpt-4o-mini")
        base_url = cfg.get("llm_base_url")

        try:
            model = OpenAIChat(id=model_id, base_url=base_url) if base_url else OpenAIChat(id=model_id)
        except TypeError:
            model = OpenAIChat(id=model_id)

        agent = Agent(model=model, instructions="Summarize market-related news context")
        resp = await agent.arun(query)
        return str(resp.content)