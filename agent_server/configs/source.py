import os


def _env_int(name: str, default: int = 0) -> int:
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return int(v)
    except Exception:
        return default


def _pick_candidate(candidates: list[dict], index: int, default_index: int = 0) -> dict:
    if not candidates:
        return {}
    if index < 0 or index >= len(candidates):
        index = default_index
    return candidates[index]


# 与 1.txt 前 5 条一致（Dashscope OpenAI-compatible）
_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DASHSCOPE_API_KEY = "sk-20cfe32740c845d1a3d491ec91d3f61b"
_DASHSCOPE_QWEN_CANDIDATES = [
    {
        "model_id": "qwen-plus-character",
        "llm_base_url": _DASHSCOPE_BASE_URL,
        "llm_api_key": _DASHSCOPE_API_KEY,
    },
    {
        "model_id": "qwen-flash-character",
        "llm_base_url": _DASHSCOPE_BASE_URL,
        "llm_api_key": _DASHSCOPE_API_KEY,
    },
    {
        "model_id": "qwen3.5-122b-a10b",
        "llm_base_url": _DASHSCOPE_BASE_URL,
        "llm_api_key": _DASHSCOPE_API_KEY,
    },
    {
        "model_id": "qwen3.5-27b",
        "llm_base_url": _DASHSCOPE_BASE_URL,
        "llm_api_key": _DASHSCOPE_API_KEY,
    },
    {
        "model_id": "qwen3.5-35b-a3b",
        "llm_base_url": _DASHSCOPE_BASE_URL,
        "llm_api_key": _DASHSCOPE_API_KEY,
    },
]

# 除 trade_decision 外的 agent：与 1.txt 前 5 条共用，由 LLM_MODEL_INDEX 轮换
_DEPZEN_CANDIDATES = _DASHSCOPE_QWEN_CANDIDATES

# trade_decision：与 1.txt 前 5 条相同列表，由 TRADE_DECISION_MODEL_INDEX 轮换（可与 LLM_MODEL_INDEX 独立）
_TRADE_DECISION_CANDIDATES = _DASHSCOPE_QWEN_CANDIDATES


def query_db_env():
    depzen_idx = _env_int("LLM_MODEL_INDEX", 0)
    depzen_choice = _pick_candidate(_DEPZEN_CANDIDATES, depzen_idx, 0)

    td_idx = _env_int("TRADE_DECISION_MODEL_INDEX", 0)
    td_choice = _pick_candidate(_TRADE_DECISION_CANDIDATES, td_idx, 0)

    depzen_model_id = depzen_choice.get("model_id", "qwen-plus-character")
    depzen_base_url = depzen_choice.get("llm_base_url", _DASHSCOPE_BASE_URL)
    depzen_api_key = depzen_choice.get("llm_api_key", _DASHSCOPE_API_KEY)

    td_model_id = td_choice.get("model_id", "qwen-plus-character")
    td_base_url = td_choice.get("llm_base_url", _DASHSCOPE_BASE_URL)
    td_api_key = td_choice.get("llm_api_key", _DASHSCOPE_API_KEY)

    return {
        "news": {
            "model_id": depzen_model_id,
            "llm_base_url": depzen_base_url,
            "llm_api_key": depzen_api_key,
            "a2a_url": "http://localhost:10002/",
        },
        "kline": {
            "language": "zh",
            "model_id": depzen_model_id,
            "llm_base_url": depzen_base_url,
            "llm_api_key": depzen_api_key,
            "a2a_url": "http://localhost:10006/",
        },
        "market_structure": {
            "language": "zh",
            "model_id": depzen_model_id,
            "llm_base_url": depzen_base_url,
            "llm_api_key": depzen_api_key,
            "a2a_url": "http://localhost:10007/",
        },
        "human_market_narrator": {
            "language": "zh",
            "model_id": depzen_model_id,
            "llm_base_url": depzen_base_url,
            "llm_api_key": depzen_api_key,
            "a2a_url": "http://localhost:10007/",
        },
        "signal_validation": {
            "language": "zh",
            "model_id": depzen_model_id,
            "llm_base_url": depzen_base_url,
            "llm_api_key": depzen_api_key,
            "a2a_url": "http://localhost:10007/",
        },
        "position_risk": {
            "language": "zh",
            "model_id": depzen_model_id,
            "llm_base_url": depzen_base_url,
            "llm_api_key": depzen_api_key,
            "a2a_url": "http://localhost:10007/",
        },
        "event_summary": {
            "language": "zh",
            "model_id": depzen_model_id,
            "llm_base_url": depzen_base_url,
            "llm_api_key": depzen_api_key,
            "a2a_url": "http://localhost:10007/",
        },
        "trade_summary": {
            "language": "zh",
            "model_id": depzen_model_id,
            "llm_base_url": depzen_base_url,
            "llm_api_key": depzen_api_key,
            "a2a_url": "http://localhost:10007/",
        },
        "trade_behavior": {
            "language": "zh",
            "model_id": depzen_model_id,
            "llm_base_url": depzen_base_url,
            "llm_api_key": depzen_api_key,
            "a2a_url": "http://localhost:10007/",
        },
        "decision": {
            "language": "zh",
            "model_id": depzen_model_id,
            "llm_base_url": depzen_base_url,
            "llm_api_key": depzen_api_key,
            "a2a_url": "http://localhost:10007/",
        },
        "trade_decision": {
            "language": "zh",
            "model_id": td_model_id,
            "llm_base_url": td_base_url,
            "llm_api_key": td_api_key,
            "theory_type": "wave",
        },
    }


def get_agent_config(name: str):
    data = query_db_env()
    return data.get(name, {})
