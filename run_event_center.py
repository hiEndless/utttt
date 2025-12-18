"""
事件中心启动脚本
从项目根目录运行: python run_event_center.py
"""
import sys
import os

# 确保项目根目录在 Python 路径中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 现在可以正常导入
if __name__ == '__main__':
    import asyncio
    from event_center.main import main
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

