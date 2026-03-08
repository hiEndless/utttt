"""
LLM 专家层（Experts）

只负责：
- 构造输入（基于 contracts 的结构化对象）
- 调用模型（通过可替换的 LLM client port）
- 产出结构化结果（contracts），并交给 workflow/domain 决策
"""

