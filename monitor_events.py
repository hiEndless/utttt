#!/usr/bin/env python3
"""
事件中心监控脚本
实时监听 Redis 中的事件流，显示事件详情
"""
import redis
import json
import time
from datetime import datetime
from typing import Dict, Any

# Redis 配置（从环境变量或直接配置）
REDIS_HOST = "38.147.173.111"
REDIS_PORT = 6379
REDIS_PASSWORD = "112233Ww.."
REDIS_DB = 8

# 要监听的流
STREAMS = {
    "raw_event_stream": "原始事件流",
    "l0_events": "L0级别事件",
    "l1_events": "L1级别事件",
    "final_events": "最终事件流",
}

# 事件级别颜色映射
LEVEL_COLORS = {
    "1": "\033[90m",  # 灰色
    "2": "\033[37m",  # 白色
    "3": "\033[33m",  # 黄色
    "4": "\033[31m",  # 红色
    "5": "\033[35m",  # 紫色
}
RESET = "\033[0m"

# 事件来源颜色
SOURCE_COLORS = {
    "alerts_consumer": "\033[36m",  # 青色
    "force_stats_consumer": "\033[32m",  # 绿色
    "indicators_event_generator": "\033[34m",  # 蓝色
}


def format_timestamp(ts_ms: str) -> str:
    """格式化时间戳"""
    try:
        ts = int(ts_ms) / 1000
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts_ms


def format_event(event: Dict[str, str]) -> str:
    """格式化事件信息"""
    lines = []
    
    # 基本信息
    event_id = event.get("event_id", "N/A")
    symbol = event.get("symbol", "N/A")
    event_type = event.get("event_type", "N/A")
    event_level = event.get("event_level", "1")
    source = event.get("source", "N/A")
    timestamp = format_timestamp(event.get("timestamp", "0"))
    
    # 颜色
    level_color = LEVEL_COLORS.get(event_level, RESET)
    source_color = SOURCE_COLORS.get(source, RESET)
    
    # 标题行
    lines.append(f"{'='*80}")
    lines.append(f"{level_color}[Level {event_level}]{RESET} {source_color}[{source}]{RESET} {timestamp}")
    lines.append(f"事件ID: {event_id}")
    lines.append(f"交易对: {symbol} | 类型: {event_type}")
    
    # Payload 详情
    payload_str = event.get("payload", "{}")
    try:
        payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        if payload:
            lines.append(f"详情:")
            # 格式化 payload，限制长度
            payload_formatted = json.dumps(payload, indent=2, ensure_ascii=False)
            # 如果太长，只显示前500字符
            if len(payload_formatted) > 500:
                payload_formatted = payload_formatted[:500] + "\n... (已截断)"
            lines.append(payload_formatted)
    except:
        lines.append(f"Payload: {payload_str[:200]}")
    
    lines.append(f"{'='*80}\n")
    
    return "\n".join(lines)


def get_stream_info(r: redis.Redis, stream_name: str) -> Dict[str, Any]:
    """获取流的基本信息"""
    try:
        length = r.xlen(stream_name)
        if length > 0:
            # 获取最新一条
            latest = r.xrevrange(stream_name, count=1)
            if latest:
                return {
                    "length": length,
                    "has_data": True,
                    "latest_id": latest[0][0] if latest else None
                }
        return {"length": length, "has_data": False, "latest_id": None}
    except Exception as e:
        return {"error": str(e)}


def monitor_streams(r: redis.Redis, stream_name: str = "raw_event_stream", last_id: str = "$"):
    """监听指定流的新事件"""
    print(f"\n{'='*80}")
    print(f"开始监听: {stream_name}")
    print(f"按 Ctrl+C 停止")
    print(f"{'='*80}\n")
    
    try:
        while True:
            # 阻塞式读取新消息
            messages = r.xread({stream_name: last_id}, count=10, block=5000)
            
            if messages:
                stream, entries = messages[0]
                for entry_id, fields in entries:
                    last_id = entry_id
                    # 转换为字典格式
                    event = {k.decode() if isinstance(k, bytes) else k: 
                            v.decode() if isinstance(v, bytes) else v 
                            for k, v in fields.items()}
                    
                    print(format_event(event))
    except KeyboardInterrupt:
        print(f"\n\n停止监听")
    except Exception as e:
        print(f"\n错误: {e}")


def show_summary(r: redis.Redis):
    """显示所有流的摘要信息"""
    print(f"\n{'='*80}")
    print(f"事件流摘要 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    for stream_name, description in STREAMS.items():
        info = get_stream_info(r, stream_name)
        if "error" in info:
            print(f"❌ {stream_name} ({description}): 错误 - {info['error']}")
        else:
            status = "✅" if info["has_data"] else "⚪"
            print(f"{status} {stream_name} ({description})")
            print(f"   长度: {info['length']}")
            if info.get("latest_id"):
                print(f"   最新ID: {info['latest_id']}")
            print()
    
    print(f"{'='*80}\n")


def main():
    """主函数"""
    print("正在连接 Redis...")
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=5
        )
        # 测试连接
        r.ping()
        print("✅ Redis 连接成功\n")
    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
        return
    
    # 显示摘要
    show_summary(r)
    
    # 询问用户要监听哪个流
    print("可监听的流:")
    stream_list = list(STREAMS.keys())
    for i, (stream_name, desc) in enumerate(STREAMS.items(), 1):
        info = get_stream_info(r, stream_name)
        length = info.get("length", 0)
        print(f"  {i}. {stream_name} ({desc}) - 当前长度: {length}")
    
    print(f"  {len(stream_list) + 1}. 监听所有流（轮询模式）")
    print(f"  0. 仅显示摘要，不监听")
    
    try:
        choice = input("\n请选择 (默认: 1): ").strip() or "1"
        
        if choice == "0":
            print("\n仅显示摘要，退出。")
            return
        
        if choice == str(len(stream_list) + 1):
            # 监听所有流（轮询模式）
            print("\n轮询模式：每5秒检查所有流的新消息\n")
            last_ids = {stream: "$" for stream in stream_list}
            
            try:
                while True:
                    for stream_name in stream_list:
                        messages = r.xread({stream_name: last_ids[stream_name]}, count=5, block=1000)
                        if messages:
                            stream, entries = messages[0]
                            for entry_id, fields in entries:
                                last_ids[stream_name] = entry_id
                                event = {k.decode() if isinstance(k, bytes) else k: 
                                        v.decode() if isinstance(v, bytes) else v 
                                        for k, v in fields.items()}
                                print(f"\n[{STREAMS[stream_name]}]")
                                print(format_event(event))
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n\n停止监听")
        else:
            # 监听单个流
            idx = int(choice) - 1
            if 0 <= idx < len(stream_list):
                stream_name = stream_list[idx]
                monitor_streams(r, stream_name)
            else:
                print("无效选择")
    except KeyboardInterrupt:
        print("\n\n退出")
    except ValueError:
        print("无效输入")
    except Exception as e:
        print(f"\n错误: {e}")


if __name__ == "__main__":
    main()

