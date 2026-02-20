#!/usr/bin/env python3
"""
测试 trading:open_positions 清理逻辑
- 检查 trade_redis (db8) 中的 trading:* 状态
- 调用 analysis([]) 模拟空持仓
- 验证清理结果
"""
import os
import sys

# 确保项目根在 path 中
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _root)

from data_server.binance.ws_binance.utils.redis_client import get_trade_sync_redis, get_sync_redis
from data_server.binance.ws_binance.utils.binance_pos_analysis import BinanceAnalysisService


def main():
    try:
        trade_conn = get_trade_sync_redis()
        trade_conn.ping()
    except Exception as e:
        print(f"Redis 连接失败: {e}")
        print("请确保 Redis 已启动，且 TRADE_REDIS_* 或 REDIS_* 环境变量正确")
        return 1
    print("=== 清理前 (trade_redis db8) ===")
    for key in ["trading:open_positions:binance", "trading:orders:binance"]:
        ktype = trade_conn.type(key)
        if ktype == "none" or ktype == b"none":
            print(f"  {key}: (不存在)")
        elif ktype == "set" or ktype == b"set":
            members = trade_conn.smembers(key)
            print(f"  {key}: set, 成员={members}")
        else:
            print(f"  {key}: type={ktype}")

    print("\n>>> 调用 analysis([]) 模拟空持仓 <<<")
    svc = BinanceAnalysisService()
    svc.analysis([])

    print("\n=== 清理后 (trade_redis db8) ===")
    for key in ["trading:open_positions:binance", "trading:orders:binance"]:
        ktype = trade_conn.type(key)
        if ktype == "none" or ktype == b"none":
            print(f"  {key}: (已删除/不存在)")
        elif ktype == "set" or ktype == b"set":
            members = trade_conn.smembers(key)
            print(f"  {key}: set, 成员={members}")
        else:
            print(f"  {key}: type={ktype}")

    open_pos = trade_conn.exists("trading:open_positions:binance")
    print(f"\n✓ trading:open_positions:binance 已清理" if not open_pos else "✗ 仍存在")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
