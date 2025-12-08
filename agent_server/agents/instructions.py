import os


def _load_prompt(agent_name: str) -> str:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    p = os.path.join(base_dir, "configs", "prompts", f"{agent_name}.txt")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return agent_name


def build_instruction(agent_name: str, task: str = None) -> str:
    agent_prompt = _load_prompt(agent_name)
    schema = (
        "Respond in JSON only. Return an object with keys: "
        "agent, task, content, confidence, rationale, metrics, sources, tool_calls, timestamp. "
        "agent: string; task: string; content: {summary: string, details: string}; "
        "confidence: number 0-1; rationale: string; metrics: object of key-number pairs; "
        "sources: array of strings; tool_calls: array of strings; timestamp: ISO8601 string. "
        "No markdown, no code fences, no extra text."
    )
    if not task:
        return agent_prompt + " " + schema
    return agent_prompt + " " + task + " " + schema