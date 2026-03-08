"""
工作流编排（Workflows）

工作流职责：
- 串联数据获取、领域策略、LLM 专家（如需要）
- 组装结构化输出并写入存储（通过 ports/adapters）

约束：
- 不直接触碰 Redis/DB/HTTP 等具体实现
"""

