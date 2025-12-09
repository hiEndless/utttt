def query_db_env():
    return {
        "news": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10002/",
        },
        "technical": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10001/",
        },
        "risk": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10003/",
        },
        "portfolio": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10004/",
        },
        "reflection": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10005/",
        },
        "fusion": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10006/",
        },
        "memory": {
            "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10007/",
        },
        "kline": {
            "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10006/",
        },
    }


def get_agent_config(name: str):
    data = query_db_env()
    return data.get(name, {})