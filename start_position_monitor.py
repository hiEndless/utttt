"""
实时仓位监控服务启动脚本
用于测试仓位监控功能
"""
import asyncio
import logging
from agent_server.utils.position_monitor import PositionMonitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

async def main():
    # 创建监控服务，每60秒检查一次
    monitor = PositionMonitor(check_interval=60)
    await monitor.start()
    
    try:
        # 保持运行
        print("=" * 60)
        print("仓位监控服务已启动")
        print(f"检查间隔: {monitor.check_interval}秒")
        print("按Ctrl+C停止")
        print("=" * 60)
        await asyncio.sleep(3600 * 24)  # 运行24小时
    except KeyboardInterrupt:
        print("\n正在停止监控服务...")
    finally:
        await monitor.stop()
        print("监控服务已停止")

if __name__ == "__main__":
    asyncio.run(main())
