"""
应用层（Application）

包含用例（use-cases）与工作流编排（workflows），只依赖：
- domain（领域模型与确定性策略）
- ports（外部依赖抽象）
"""

from .bootstrap import create_trade_event_workflow_from_env
from .http_app import create_app as create_http_app

__all__ = [
    "create_trade_event_workflow_from_env",
    "create_http_app",
]
