#!/usr/bin/env python3
"""
检查事件中心的数据源状态
诊断为什么没有新事件产生
"""
import redis
import json
from datetime import datetime

REDIS_HOST = "38.147.173.111"
REDIS_PORT = 6379
REDIS_PASSWORD = "112233Ww.."
REDIS_DB = 8

def check_stream(r, pattern, description):
    """检查流的状态"""
    print(f"\n{'='*60}")
    print(f"检查: {description}")
    print(f"模式: {pattern}")
    print(f"{'='*60}")
    
    try:
        cursor = 0
        keys = []
        while True:
            cursor, batch = r.scan(cursor=cursor, match=pattern, count=200)
            keys.extend(batch)
            if cursor == 0:
                break
        
        if not keys:
            print(f"❌ 未找到匹配的流")
            return []
        
        print(f"✅ 找到 {len(keys)} 个流:")
        results = []
        for key in keys:
            try:
                length = r.xlen(key)
                if length > 0:
                    latest = r.xrevrange(key, count=1)
                    latest_id = latest[0][0] if latest else "N/A"
                    latest_time = latest[0][1].get('ts', 'N/A') if latest and latest[0][1] else 'N/A'
                    print(f"  - {key}: 长度={length}, 最新ID={latest_id}, 最新时间={latest_time}")
                    results.append({
                        "key": key,
                        "length": length,
                        "latest_id": latest_id,
                        "has_data": True
                    })
                else:
                    print(f"  - {key}: 长度=0 (空流)")
                    results.append({
                        "key": key,
                        "length": 0,
                        "has_data": False
                    })
            except Exception as e:
                print(f"  - {key}: 错误 - {e}")
                results.append({"key": key, "error": str(e)})
        
        return results
    except Exception as e:
        print(f"❌ 错误: {e}")
        return []


def check_indicators(r):
    """检查技术指标数据"""
    print(f"\n{'='*60}")
    print(f"检查: 技术指标数据")
    print(f"{'='*60}")
    
    pattern = "indicators:binance:*"
    try:
        cursor = 0
        keys = []
        while True:
            cursor, batch = r.scan(cursor=cursor, match=pattern, count=200)
            keys.extend(batch)
            if cursor == 0:
                break
        
        if not keys:
            print(f"❌ 未找到技术指标数据")
            print(f"   提示: 需要运行 REST 服务来生成指标数据")
            return False
        
        print(f"✅ 找到 {len(keys)} 个指标键:")
        for key in keys[:10]:  # 只显示前10个
            try:
                val = r.get(key)
                if val:
                    data = json.loads(val)
                    print(f"  - {key}: 有数据 (类型: {type(data).__name__})")
                else:
                    print(f"  - {key}: 空")
            except Exception as e:
                print(f"  - {key}: 错误 - {e}")
        
        if len(keys) > 10:
            print(f"  ... 还有 {len(keys) - 10} 个键")
        
        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def check_klines(r):
    """检查K线数据"""
    print(f"\n{'='*60}")
    print(f"检查: K线数据")
    print(f"{'='*60}")
    
    pattern = "klines:binance:*"
    try:
        cursor = 0
        keys = []
        while True:
            cursor, batch = r.scan(cursor=cursor, match=pattern, count=200)
            keys.extend(batch)
            if cursor == 0:
                break
        
        if not keys:
            print(f"❌ 未找到K线数据")
            print(f"   提示: 需要运行 REST 服务来生成K线数据")
            return False
        
        print(f"✅ 找到 {len(keys)} 个K线键:")
        for key in keys[:10]:  # 只显示前10个
            try:
                val = r.get(key)
                if val:
                    data = json.loads(val)
                    if isinstance(data, list):
                        print(f"  - {key}: 有数据 ({len(data)} 条K线)")
                    else:
                        print(f"  - {key}: 有数据 (类型: {type(data).__name__})")
                else:
                    print(f"  - {key}: 空")
            except Exception as e:
                print(f"  - {key}: 错误 - {e}")
        
        if len(keys) > 10:
            print(f"  ... 还有 {len(keys) - 10} 个键")
        
        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def main():
    print("="*60)
    print("事件中心数据源诊断工具")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=5
        )
        r.ping()
        print("✅ Redis 连接成功\n")
    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
        return
    
    # 检查各个数据源
    alerts_streams = check_stream(r, "alerts:binance:*", "市场告警流 (AlertsConsumer 的数据源)")
    force_stats_streams = check_stream(r, "force_stats_stream:binance:*", "强平统计流 (ForceStatsConsumer 的数据源)")
    has_indicators = check_indicators(r)
    has_klines = check_klines(r)
    
    # 总结
    print(f"\n{'='*60}")
    print("诊断总结")
    print(f"{'='*60}")
    
    alerts_has_data = any(s.get("has_data", False) for s in alerts_streams)
    force_stats_has_data = any(s.get("has_data", False) for s in force_stats_streams)
    
    print(f"\n数据源状态:")
    print(f"  {'✅' if alerts_has_data else '❌'} 市场告警流: {'有数据' if alerts_has_data else '无数据'}")
    print(f"  {'✅' if force_stats_has_data else '❌'} 强平统计流: {'有数据' if force_stats_has_data else '无数据'}")
    print(f"  {'✅' if has_indicators else '❌'} 技术指标数据: {'有数据' if has_indicators else '无数据'}")
    print(f"  {'✅' if has_klines else '❌'} K线数据: {'有数据' if has_klines else '无数据'}")
    
    print(f"\n事件中心运行周期说明:")
    print(f"  1. AlertsConsumer:")
    print(f"     - 每 5 秒扫描一次 alerts:binance:* 流")
    print(f"     - 阻塞读取新消息（最多等待 3 秒）")
    print(f"     - 限频: 同类型事件至少间隔 1 秒")
    print(f"     - 配额: 60 秒内每个 symbol 最多 1 个事件（level < 5）")
    
    print(f"\n  2. ForceStatsConsumer:")
    print(f"     - 每 5 秒扫描一次 force_stats_stream:binance:* 流")
    print(f"     - 阻塞读取新消息（最多等待 3 秒）")
    print(f"     - 去抖: 30 秒内同类型事件不重复")
    print(f"     - 配额: 30 秒内每个 symbol 最多 1 个事件（level < 4）")
    
    print(f"\n  3. IndicatorsScheduler:")
    print(f"     - 1m: 每 20 秒处理一次")
    print(f"     - 5m: 每 150 秒 (2.5分钟) 处理一次")
    print(f"     - 15m: 每 300 秒 (5分钟) 处理一次")
    print(f"     - 30m: 每 600 秒 (10分钟) 处理一次")
    print(f"     - 1h: 每 900 秒 (15分钟) 处理一次")
    print(f"     - 2h: 每 1800 秒 (30分钟) 处理一次")
    print(f"     - 4h: 每 3600 秒 (1小时) 处理一次")
    print(f"     - 1d: 每 43200 秒 (12小时) 处理一次")
    print(f"     - 限频: 1m周期至少间隔30秒, 5m周期至少间隔60秒...")
    print(f"     - 配额: 1m周期120秒内最多1个, 5m周期300秒内最多1个...")
    
    print(f"\n建议:")
    if not alerts_has_data:
        print(f"  ⚠️  市场告警流无数据，检查 WebSocket 服务是否正常运行")
    if not force_stats_has_data:
        print(f"  ⚠️  强平统计流无数据，检查 WebSocket 服务是否正常生成强平数据")
    if not has_indicators or not has_klines:
        print(f"  ⚠️  技术指标/K线数据缺失，需要运行 REST 服务来生成数据")
    if alerts_has_data or force_stats_has_data or has_indicators:
        print(f"  ✅ 数据源正常，如果没有新事件，可能是限频/配额控制导致的")
        print(f"     可以等待更长时间，或者检查事件级别是否满足条件")


if __name__ == "__main__":
    main()

