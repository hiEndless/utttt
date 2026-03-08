"""
agent_server_new

目标：
- 在既有 agent_server 的基础上重新设计可持续迭代的多 agent 服务架构
- 强化契约（contracts）与端口（ports），降低 workflow 与 infra 的耦合

说明：
- 该包用于“推翻重来”的新实现；短期内允许通过 compat/adapters 复用 agent_server 旧代码
"""

