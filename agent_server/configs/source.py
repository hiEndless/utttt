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
            "language": "zh",
            "model_id": "qwen3-max",
            "llm_base_url": "https://apis.iflow.cn/v1/chat/completions",
            "llm_api_key": "sk-67f7879452d92f3b4f56e530ce7b46b9",
            "a2a_url": "http://localhost:10006/",
        },
        "market_structure": {
            "language": "zh",
            "model_id": "qwen3-max",
            "llm_base_url": "https://apis.iflow.cn/v1/chat/completions",
            "llm_api_key": "sk-67f7879452d92f3b4f56e530ce7b46b9",
            "a2a_url": "http://localhost:10007/",
        },
        "human_market_narrator": {
            "language": "zh",
            "model_id": "qwen3-max",
            "llm_base_url": "https://apis.iflow.cn/v1/chat/completions",
            "llm_api_key": "sk-67f7879452d92f3b4f56e530ce7b46b9",
            "a2a_url": "http://localhost:10007/",
        },
        "signal_validation": {
            "language": "zh",
            "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10007/",
        },
        "position_risk": {
            "language": "zh",
            "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10007/",
        },
        "event_summary": {
            "language": "zh",
            "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10007/",
        },
        "trade_summary": {
            "language": "zh",
            "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10007/",
        },
        "trade_behavior": {
            "language": "zh",
            "model_id": "qwen3-max",
            "llm_base_url": "https://apis.iflow.cn/v1/chat/completions",
            "llm_api_key": "sk-67f7879452d92f3b4f56e530ce7b46b9",
            "a2a_url": "http://localhost:10007/",
        },
        "decision": {
            "language": "zh",
            "model_id": "qwen3-max",
            "llm_base_url": "https://apis.iflow.cn/v1/chat/completions",
            "llm_api_key": "sk-67f7879452d92f3b4f56e530ce7b46b9",
            "a2a_url": "http://localhost:10007/",
        },
    }


def get_agent_config(name: str):
    data = query_db_env()
    return data.get(name, {})