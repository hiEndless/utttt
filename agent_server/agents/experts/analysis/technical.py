class TechnicalExpert:
    name = "technical"

    async def run(self, query: str) -> str:
        from agno.agent import Agent
        from agno.models.openai import OpenAILike
        from agent_server.configs.source import get_agent_config
        from agent_server.agents.instructions import build_instruction
        import json
        from agent_server.tools import web_json, calc_rsi

        cfg = get_agent_config(self.name)

        model_id = str(cfg.get("model_id") or "").strip()
        base_url = str(cfg.get("llm_base_url") or "").strip() or None
        api_key = str(cfg.get("llm_api_key") or "").strip() or None
        missing_keys: list[str] = []
        if not model_id:
            missing_keys.append("model_id")
        if not base_url:
            missing_keys.append("llm_base_url")
        if not api_key:
            missing_keys.append("llm_api_key")
        if missing_keys:
            return json.dumps({"error": "agent_config_missing", "missing": missing_keys}, ensure_ascii=False)

        try:
            model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key) if (base_url or api_key) else OpenAILike(id=model_id)
        except TypeError:
            model = OpenAILike(id=model_id)

        agent = Agent(model=model, instructions=build_instruction(self.name, "Analyze technical indicators and trend context"), tools=[web_json, calc_rsi])
        resp = await agent.arun(query)
        return str(resp.content)
