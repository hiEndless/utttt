#!/usr/bin/env python3
"""
根据真实仓位同步 trading:open_positions，清理已平仓的 symbol
用法: python -m agent_server.scripts.sync_open_positions [--exchange binance] [--clear-all]
"""
import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


async def main():
    parser = argparse.ArgumentParser(description="同步 trading:open_positions 与真实仓位")
    parser.add_argument("--exchange", default="binance", help="交易所")
    parser.add_argument("--clear-all", action="store_true", help="清空整个集合（慎用，用于重置脏数据）")
    args = parser.parse_args()

    if args.clear_all:
        from agent_server.utils.position_sync import clear_all_open_positions
        ok = clear_all_open_positions(args.exchange)
        print("✅ 已清空" if ok else "❌ 清空失败")
        return

    from agent_server.utils.position_sync import sync_open_positions_with_reality
    cleared = await sync_open_positions_with_reality(args.exchange)
    print(f"✅ 同步完成，清理 {cleared} 个已平仓 symbol")


if __name__ == "__main__":
    asyncio.run(main())
