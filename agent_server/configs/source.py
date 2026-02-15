def query_db_env():
    return {
        "news": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10002/",
        },
        "kline": {
            "language": "zh",
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10006/",
        },
        "market_structure": {
            "language": "zh",
            "model_id": "deepseek-v3",
            "llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
            "a2a_url": "http://localhost:10007/",
        },
        "human_market_narrator": {
            "language": "zh",
            "model_id": "deepseek-v3",
            "llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
            "a2a_url": "http://localhost:10007/",
        },
        "signal_validation": {
            "language": "zh",
            "model_id": "deepseek-v3",
            "llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
            "a2a_url": "http://localhost:10007/",
        },
        "position_risk": {
            "language": "zh",
            "model_id": "deepseek-v3",
            "llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
            "a2a_url": "http://localhost:10007/",
        },
        "event_summary": {
            "language": "zh",
            "model_id": "deepseek-v3",
            "llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
            "a2a_url": "http://localhost:10007/",
        },
        "trade_summary": {
            "language": "zh",
            "model_id": "deepseek-v3",
            "llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
            "a2a_url": "http://localhost:10007/",
        },
        "trade_behavior": {
            "language": "zh",
            "model_id": "deepseek-v3",
            "llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
            "a2a_url": "http://localhost:10007/",
        },
        "decision": {
            "language": "zh",
            "model_id": "deepseek-v3",
            "llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
            "a2a_url": "http://localhost:10007/",
        },
        "trade_decision": {
            "language": "zh",
            "model_id": "deepseek-v3",
            "llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
            "theory_type": "wave",
        },
    }


def get_agent_config(name: str):
    data = query_db_env()
    return data.get(name, {})