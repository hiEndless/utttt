from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.agents.instructions import build_instruction
import os
from agent_server.tools import get_force_stats


class ForceStatsExpert:
    name = "force_stats"

    async def run(self, query: str) -> str:

        cfg = get_agent_config(self.name)

        model_id = cfg.get("model_id", "deepseek-ai/DeepSeek-V3")
        base_url = cfg.get("llm_base_url")
        api_key = cfg.get("llm_api_key") or os.getenv("SILICONFLOW_TOKEN")

        model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key)

        agent = Agent(model=model,
                      instructions=build_instruction(self.name),
                      tools=[get_force_stats])
        resp = await agent.arun(query)
        return str(resp.content)
