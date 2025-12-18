"""
REST API 数据抓取服务启动脚本
从项目根目录运行: python run_rest.py
"""
import sys
import os

# 确保项目根目录在 Python 路径中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 切换到 rest_binance/app 目录（因为 main.py 使用相对导入）
rest_dir = os.path.join(project_root, 'data_server', 'binance', 'rest_binance',
                        'app')
original_dir = os.getcwd()

try:
    os.chdir(rest_dir)
    # 添加当前目录到 Python 路径，确保相对导入正常工作
    if rest_dir not in sys.path:
        sys.path.insert(0, rest_dir)

    # 导入并运行
    from main import main
    main()
except KeyboardInterrupt:
    print("\n服务已停止")
except Exception as e:
    print(f"\n✗ 启动失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    # 恢复原始目录
    os.chdir(original_dir)
