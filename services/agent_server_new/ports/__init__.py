"""
端口层（Ports）

用于隔离基础设施依赖（Redis/DB/HTTP/第三方交易所等）。
workflow 与 domain 只依赖 ports 的抽象接口，不依赖具体实现。
"""

