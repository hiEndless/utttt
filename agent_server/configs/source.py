def query_db_env():
    return {
        "news": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key":
            "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10002/",
        },
        "technical": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key":
            "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10001/",
        },
        "risk": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key":
            "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10003/",
        },
        "portfolio": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key":
            "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10004/",
        },
        "reflection": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key":
            "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10005/",
        },
        "fusion": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key":
            "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10006/",
        },
        "memory": {
            "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key":
            "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10007/",
        },
        "kline": {
            # "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
            # "llm_base_url": "https://api.siliconflow.cn/v1",
            # "llm_api_key":
            # "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "model_id": "deepseek-v3",
            "llm_base_url":
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
            "a2a_url": "http://localhost:10006/",
        },
        "market_structure": {
            # "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
            # "llm_base_url": "https://api.siliconflow.cn/v1",
            # "llm_api_key":
            # "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            # deepseek
            "model_id": "deepseek-v3",
            "llm_base_url":
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
            "a2a_url": "http://localhost:10007/",
        },
        "signal_validation": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key":
            "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10007/",
        },
        "position_risk": {
            "model_id": "deepseek-ai/DeepSeek-V3",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key":
            "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10007/",
        },
        "trade_decision": {
            # lcy
            # "model_id": "deepseek-ai/DeepSeek-V3",
            # "llm_base_url": "https://api.siliconflow.cn/v1",
            # "llm_api_key":
            # "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            # deepseek
            "model_id": "deepseek-v3",
            "llm_base_url":
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
            "a2a_url": "http://localhost:10008/",
            # 理论类型选择: "wave" (波浪理论) 或 "chan" (缠论) 或 None (默认)
            "theory_type":
            "wave",  # 设置为 "wave" 使用波浪理论, "chan" 使用缠论, None 使用默认理论
            # ModelScope  阿里云推出的模型服务平台
            # "model_id": "deepseek-ai/DeepSeek-V3.2",
            # "llm_base_url": "https://api-inference.modelscope.cn/v1",
            # "llm_api_key": "ms-b3ea64d3-5c65-4146-aec9-5dddd1cb5ee7",
            # "a2a_url": "http://localhost:10008/",
            # DashScope (通义千问)
            # "model_id": "deepseek-v3.2",
            # "llm_base_url":
            # "https://dashscope.aliyuncs.com/compatible-mode/v1",
            # "llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
            # "a2a_url": "http://localhost:10008/",
            # deepseek
            # "model_id": "deepseek-chat",
            # "llm_base_url":
            # "https://api.deepseek.com/v1",
            # "llm_api_key": "sk-98e1a74bf9e74352bf28ea11115a637a",
            # "a2a_url": "http://localhost:10008/",
            # Qwen (通义千问)
            # "model_id": "qwen3-max",
            # "llm_base_url":
            # "https://dashscope.aliyuncs.com/compatible-mode/v1",
            # "llm_api_key": "sk-9e17aabeaeca4a5b8a6dce517de0d8a7",
            # "a2a_url": "http://localhost:10008/",
        },
        "event_summary": {
            "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key":
            "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10007/",
        },
        "trade_summary": {
            "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key":
            "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10007/",
        },
        "trade_event": {
            "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "llm_base_url": "https://api.siliconflow.cn/v1",
            "llm_api_key":
            "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
            "a2a_url": "http://localhost:10007/",
        },
    }


def get_agent_config(name: str):
    data = query_db_env()
    return data.get(name, {})
