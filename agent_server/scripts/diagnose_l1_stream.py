#!/usr/bin/env python3
"""
诊断 l1_events stream 与 trade 消费组状态
用法: python -m agent_server.scripts.diagnose_l1_stream
"""
import asyncio
import os
import sys

# 确保 agent_server 在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import redis.asyncio as aioredis
from agent_server.config import settings


async def main():
    password = settings.redis_password
    if isinstance(password, str) and password.strip().lower() in ("none", "null", "", "undefined"):
        password = None

    print("=" * 60)
    print("L1 Stream 诊断")
    print("=" * 60)
    print(f"Redis: {settings.redis_host}:{settings.redis_port} db={settings.redis_db}")
    print(f"Stream: l1_events")
    print()

    client = aioredis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=password,
        decode_responses=True,
    )

    try:
        await client.ping()
        print("[OK] Redis 连接成功")
    except Exception as e:
        print(f"[FAIL] Redis 连接失败: {e}")
        return

    try:
        stream_len = await client.xlen("l1_events")
        print(f"[OK] l1_events XLEN = {stream_len}")
        if stream_len == 0:
            print("  -> 若你确认有上百条数据，请检查 REDIS_DB 是否与 event_center 一致（默认 1）")
            print("  -> redis-cli 查看时需: redis-cli -n 1 或 SELECT 1")
    except Exception as e:
        print(f"[FAIL] XLEN l1_events 失败: {e}")
        print("  -> 可能 stream 不存在，或 Redis DB 不对（event_center 默认 db=1）")
        return

    try:
        groups = await client.xinfo_groups("l1_events")
        print(f"\n消费组数量: {len(groups)}")
        for g in groups:
            name = g.get("name", "")
            last_id = g.get("last-delivered-id", "")
            pending = g.get("pending", 0)
            consumers = g.get("consumers", 0)
            print(f"  - {name}: last_id={last_id} pending={pending} consumers={consumers}")
    except Exception as e:
        print(f"[WARN] XINFO GROUPS 失败: {e}")

    # 尝试读取一条（不 ack，用 XRANGE 看最新）
    try:
        entries = await client.xrevrange("l1_events", count=1)
        if entries:
            eid, fields = entries[0]
            symbol = fields.get("symbol", "")
            event_id = fields.get("event_id", "")
            print(f"\n最新一条: entry_id={eid} symbol={symbol} event_id={event_id[:50]}...")
        else:
            print("\nstream 为空")
    except Exception as e:
        print(f"[WARN] XREVRANGE 失败: {e}")

    # 检查 trade_l1_group 的 pending
    try:
        info = await client.xpending("l1_events", "trade_l1_group")
        if info:
            pending_count = info.get("pending", 0) if isinstance(info, dict) else 0
            if pending_count and pending_count > 0:
                print(f"\n[WARN] trade_l1_group 有 {pending_count} 条 pending (可能卡住)")
            else:
                print("\ntrade_l1_group 无 pending")
        else:
            print("\ntrade_l1_group 无 pending")
    except Exception as e:
        if "NOGROUP" in str(e):
            print("\n[INFO] trade_l1_group 尚未创建，首次运行 trade_decision_main 时会创建")
        else:
            print(f"\n[WARN] XPENDING 失败: {e}")

    # 已开仓集合（trade_listen 用此判断是否跳过 L1 事件）
    try:
        key = "trading:open_positions:binance"
        members = await client.smembers(key)
        if members:
            syms = sorted(m.decode() if isinstance(m, bytes) else str(m) for m in members)
            print(f"\n[已开仓] {key} = {syms}")
            print("  -> 这些 symbol 的 L1 事件会被 trade_listen 跳过（避免重复开仓）")
            print("  -> 若为脏数据可清空: redis-cli -n <db> DEL trading:open_positions:binance")
        else:
            print(f"\n[已开仓] {key} = 空")
    except Exception as e:
        print(f"\n[WARN] 已开仓集合检查失败: {e}")

    await client.aclose()
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
