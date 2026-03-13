"""
适配器层（Adapters）

将 ports 的抽象接口连接到具体实现：
- 复用旧 agent_server 的 RedisClient/Recorder/工具函数
- 或接入新的存储/消息队列/指标系统
"""

from .execution_service_http import HttpExecutionDecisionProvider
from .event_recorder_jsonl import JsonlEventRecorder
from .llm_agno import AgnoLLMObserver
from .llm_openai_compatible import OpenAICompatibleLLMObserver
from .position_context_execution_http import HttpExecutionPositionContextProvider

__all__ = [
    "HttpExecutionDecisionProvider",
    "HttpExecutionPositionContextProvider",
    "JsonlEventRecorder",
    "AgnoLLMObserver",
    "OpenAICompatibleLLMObserver",
]
