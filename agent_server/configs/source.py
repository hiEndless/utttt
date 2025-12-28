def query_db_env():
    """
    Agent 配置
    根据测试结果，已切换到 ModelScope API 和推荐的模型：
    - 主推荐: Qwen3-235B-Instruct (3.38秒，质量最高) - 用于关键agent
    - 推理模型: DeepSeek-R1-0528 (11.18秒) - 用于深度分析
    - 快速模型: DeepSeek-V3.2 (4.36秒) - 用于快速响应
    """
    # ModelScope API 配置
    modelscope_base_url = "https://api-inference.modelscope.cn/v1"
    modelscope_api_key = "ms-b3ea64d3-5c65-4146-aec9-5dddd1cb5ee7"
    
    # SiliconFlow API 配置（备用）
    siliconflow_base_url = "https://api.siliconflow.cn/v1"
    siliconflow_api_key = "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa"
    
    return {
        # ============================================================
        # 核心分析 Agent（使用最佳模型）
        # ============================================================
        "technical": {
            # 🥇 主推荐: Qwen3-235B-Instruct (3.38秒，质量最高)
            "model_id": "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "llm_base_url": modelscope_base_url,
            "llm_api_key": modelscope_api_key,
            "a2a_url": "http://localhost:10001/",
        },
        "risk": {
            # 🥇 主推荐: Qwen3-235B-Instruct (3.38秒，质量最高)
            "model_id": "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "llm_base_url": modelscope_base_url,
            "llm_api_key": modelscope_api_key,
            "a2a_url": "http://localhost:10003/",
        },
        "trading_decision": {
            # 🥇 主推荐: Qwen3-235B-Instruct (3.38秒，质量最高)
            # 或使用推理模型 DeepSeek-R1-0528 (11.18秒) 用于深度分析
            "model_id": "Qwen/Qwen3-235B-A22B-Instruct-2507",
            # "model_id": "deepseek-ai/DeepSeek-R1-0528",  # 推理模型，用于深度分析
            "llm_base_url": modelscope_base_url,
            "llm_api_key": modelscope_api_key,
            "a2a_url": "http://localhost:10008/",
        },
        
        # ============================================================
        # 其他 Agent（使用快速模型或保持原配置）
        # ============================================================
        "news": {
            # 🥉 快速模型: DeepSeek-V3.2 (4.36秒)
            "model_id": "deepseek-ai/DeepSeek-V3.2",
            "llm_base_url": modelscope_base_url,
            "llm_api_key": modelscope_api_key,
            "a2a_url": "http://localhost:10002/",
        },
        "portfolio": {
            # 🥉 快速模型: DeepSeek-V3.2 (4.36秒)
            "model_id": "deepseek-ai/DeepSeek-V3.2",
            "llm_base_url": modelscope_base_url,
            "llm_api_key": modelscope_api_key,
            "a2a_url": "http://localhost:10004/",
        },
        "reflection": {
            # 🥉 快速模型: DeepSeek-V3.2 (4.36秒)
            "model_id": "deepseek-ai/DeepSeek-V3.2",
            "llm_base_url": modelscope_base_url,
            "llm_api_key": modelscope_api_key,
            "a2a_url": "http://localhost:10005/",
        },
        "fusion": {
            # 🥉 快速模型: DeepSeek-V3.2 (4.36秒)
            "model_id": "deepseek-ai/DeepSeek-V3.2",
            "llm_base_url": modelscope_base_url,
            "llm_api_key": modelscope_api_key,
            "a2a_url": "http://localhost:10006/",
        },
        
        # ============================================================
        # 视觉模型 Agent（保持原配置）
        # ============================================================
        "memory": {
            "model_id": "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "llm_base_url": modelscope_base_url,
            "llm_api_key": modelscope_api_key,
            "a2a_url": "http://localhost:10007/",
        },
        "kline": {
            "model_id": "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "llm_base_url": modelscope_base_url,
            "llm_api_key": modelscope_api_key,
            "a2a_url": "http://localhost:10006/",
        },
        "market_structure": {
            "model_id": "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "llm_base_url": modelscope_base_url,
            "llm_api_key": modelscope_api_key,
            "a2a_url": "http://localhost:10007/",
        },
        # "memory": {
        #     "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
        #     "llm_base_url": siliconflow_base_url,  # 保持原API（视觉模型）
        #     "llm_api_key": siliconflow_api_key,
        #     "a2a_url": "http://localhost:10007/",
        # },
        # "kline": {
        #     "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
        #     "llm_base_url": siliconflow_base_url,  # 保持原API（视觉模型）
        #     "llm_api_key": siliconflow_api_key,
        #     "a2a_url": "http://localhost:10006/",
        # },
        # "market_structure": {
        #     "model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct",
        #     "llm_base_url": siliconflow_base_url,  # 保持原API（视觉模型）
        #     "llm_api_key": siliconflow_api_key,
        #     "a2a_url": "http://localhost:10007/",
        # },
    }


def get_agent_config(name: str):
    data = query_db_env()
    return data.get(name, {})