class RiskExpert:
    name = "risk"

    async def run(self, query: str) -> str:
        from agno.agent import Agent
        from agno.models.openai import OpenAILike
        from agent_server.configs.source import get_agent_config
        import os

        cfg = get_agent_config(self.name)

        model_id = cfg.get("model_id", "deepseek-ai/DeepSeek-V3")
        base_url = cfg.get("llm_base_url")
        api_key = cfg.get("llm_api_key") or os.getenv("SILICONFLOW_TOKEN")

        try:
            model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key) if (base_url or api_key) else OpenAILike(id=model_id)
        except TypeError:
            model = OpenAILike(id=model_id)

        agent = Agent(model=model, instructions="Assess risk exposure and scenario impacts")
        resp = await agent.arun(query)
        return str(resp.content)