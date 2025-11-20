def query_db_env():
    return {
        "news": {
            "model_id": "gpt-4o-mini",
            "llm_base_url": None,
            "a2a_url": "http://localhost:10002/",
        },
        "technical": {
            "model_id": "gpt-4o-mini",
            "llm_base_url": None,
            "a2a_url": "http://localhost:10001/",
        },
        "risk": {
            "model_id": "gpt-4o-mini",
            "llm_base_url": None,
            "a2a_url": "http://localhost:10003/",
        },
        "portfolio": {
            "model_id": "gpt-4o-mini",
            "llm_base_url": None,
            "a2a_url": "http://localhost:10004/",
        },
    }


def get_agent_config(name: str):
    data = query_db_env()
    return data.get(name, {})