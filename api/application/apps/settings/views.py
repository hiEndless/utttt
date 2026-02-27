"""
Settings 视图模块 - 已重构

所有具体的 API 路由现在都在 api/ 目录下的各个功能模块中。
此文件仅作为向后兼容的入口点，实际路由在 __init__.py 中定义。
"""

# 为了向后兼容，从 __init__.py 导入 app
from . import app