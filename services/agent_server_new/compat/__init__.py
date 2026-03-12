"""
兼容层（Compat）

短期复用旧 agent_server 的能力入口，便于渐进式迁移：
- market_structure 生成
- 现有 risk/global overlay 读取
- 现有 recorder 落库

注意：
- compat 只作为过渡层；稳定后应逐步替换为 ports+adapters 的实现。
"""

