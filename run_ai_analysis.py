#!/usr/bin/env python3
"""
AI 分析脚本
从事件中心读取事件，调用 Agent 系统进行分析，返回结果
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agent_server.events import EventSignal
from agent_server.runtime import handle_event
import redis.asyncio as aioredis


class AIAnalyzer:

    def __init__(self):
        # Redis 配置（从环境变量读取）
        self.redis_host = os.getenv("REDIS_HOST", "38.147.173.111")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD", "112233Ww..")
        self.redis_db = int(os.getenv("REDIS_DB", "8"))

        # 事件流配置
        self.streams = {
            "raw_event_stream": "原始事件流",
            "l0_events": "L0级别事件",
            "l1_events": "L1级别事件",
            "final_events": "最终事件流",
        }

        self.redis: Optional[aioredis.Redis] = None
        self.stream_offsets: Dict[str, str] = {}

    async def connect_redis(self):
        """连接 Redis"""
        try:
            self.redis = aioredis.Redis(host=self.redis_host,
                                        port=self.redis_port,
                                        password=self.redis_password,
                                        db=self.redis_db,
                                        decode_responses=True,
                                        socket_connect_timeout=5)
            await self.redis.ping()
            print(
                f"✅ Redis 连接成功: {self.redis_host}:{self.redis_port}/{self.redis_db}"
            )
            return True
        except Exception as e:
            print(f"❌ Redis 连接失败: {e}")
            return False

    async def read_event_from_stream(self,
                                     stream_name: str = "final_events",
                                     count: int = 1,
                                     read_history: bool = False) -> Optional[Dict]:
        """从事件流读取事件"""
        if not self.redis:
            return None

        try:
            # 初始化偏移量
            if stream_name not in self.stream_offsets:
                # 如果读取历史，从流的开头开始；否则只读新消息
                if read_history:
                    self.stream_offsets[stream_name] = "0-0"  # 从开头读取
                else:
                    self.stream_offsets[stream_name] = "$"  # 只读新消息

            # 读取消息
            if read_history and self.stream_offsets[stream_name] == "0-0":
                # 读取历史消息（从最新开始倒序）
                messages = await self.redis.xrevrange(
                    stream_name,
                    max="+",  # 从最新开始
                    min="-",  # 到最旧
                    count=count
                )
                
                if not messages:
                    return None
                
                # xrevrange 返回的是 (entry_id, fields) 的列表
                entry_id, fields = messages[0]  # 最新的一条
                self.stream_offsets[stream_name] = entry_id
                
                # 转换为字典
                event_data = dict(fields)
            else:
                # 读取新消息（阻塞式）
                messages = await self.redis.xread(
                    {stream_name: self.stream_offsets[stream_name]},
                    count=count,
                    block=5000  # 阻塞5秒
                )

                if not messages:
                    return None

                stream, entries = messages[0]

                if not entries:
                    return None

                # 获取最新一条消息
                entry_id, fields = entries[-1]
                self.stream_offsets[stream_name] = entry_id

                # 转换为字典
                event_data = dict(fields)

            # 解析 payload
            if "payload" in event_data:
                try:
                    event_data["payload"] = json.loads(event_data["payload"])
                except:
                    pass

            return event_data

        except Exception as e:
            print(f"❌ 读取事件失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def map_event_to_signal(self, event_data: Dict) -> EventSignal:
        """将事件数据映射为 EventSignal"""
        event_type = event_data.get("event_type", "unknown")
        event_level = event_data.get("event_level", "1")
        symbol = event_data.get("symbol", "BTCUSDT")
        payload = event_data.get("payload", {})

        # 根据事件级别确定强度
        level = int(event_level) if event_level.isdigit() else 1
        if level >= 4:
            strength = "high"
        elif level >= 3:
            strength = "medium"
        else:
            strength = "low"

        # 根据事件类型确定事件类型
        if "force_" in event_type:
            signal_type = "market_spike"
        elif "combo" in event_type:
            signal_type = "market_signal"
        elif "price" in event_type or "depth" in event_type:
            signal_type = "market_spike"
        else:
            signal_type = "market_signal"

        # 构建完整的 payload
        full_payload = {
            "event_id": event_data.get("event_id"),  # 添加 event_id
            "symbol": symbol,
            "event_type": event_type,
            "event_level": level,
            "timestamp": event_data.get("timestamp"),
            "source": event_data.get("source"),
            **payload
        }

        return EventSignal(type=signal_type,
                           payload=full_payload,
                           strength=strength)

    async def analyze_event(self, event_signal: EventSignal) -> Dict:
        """调用 Agent 系统分析事件"""
        try:
            print(f"\n{'='*60}")
            print(f"开始 AI 分析...")
            print(f"事件类型: {event_signal.type}")
            print(f"事件强度: {event_signal.strength}")
            print(f"交易对: {event_signal.payload.get('symbol')}")
            print(f"{'='*60}\n")

            # 调用 Agent 系统
            result = await handle_event(event_signal)

            return result

        except Exception as e:
            print(f"❌ AI 分析失败: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def format_result(self, result: Dict) -> str:
        """格式化分析结果"""
        output = []
        output.append(f"\n{'='*80}")
        output.append(
            f"AI 分析结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append(f"{'='*80}\n")

        if "error" in result:
            output.append(f"❌ 错误: {result['error']}")
            return "\n".join(output)

        # Agent 列表
        names = result.get("names", [])
        output.append(f"参与分析的 Agent: {', '.join(names)}\n")

        # 各 Agent 输出
        outputs = result.get("outputs", [])
        for i, (name, output_str) in enumerate(zip(names, outputs)):
            output.append(f"\n{'─'*80}")
            output.append(f"Agent: {name}")
            output.append(f"{'─'*80}")
            try:
                output_obj = json.loads(output_str)
                output.append(
                    json.dumps(output_obj, indent=2, ensure_ascii=False))
            except:
                output.append(output_str[:500])  # 限制长度
            output.append("")

        # 评分
        scores = result.get("scores", {})
        if scores:
            output.append(f"\n{'─'*80}")
            output.append("自动评分:")
            for i, score in scores.items():
                agent_name = names[int(i)] if int(i) < len(
                    names) else f"agent-{i}"
                output.append(f"  {agent_name}: {score:.2f}")

        # 权重
        weights = result.get("weights", {})
        if weights:
            output.append(f"\n{'─'*80}")
            output.append("权重分布:")
            for name, weight in weights.items():
                output.append(f"  {name}: {weight:.2%}")

        # 融合结果
        fusion = result.get("fusion")
        if fusion:
            output.append(f"\n{'─'*80}")
            output.append("融合结果:")
            output.append(f"{'─'*80}")
            output.append(fusion[:1000])  # 限制长度

        # 反思结果
        reflection = result.get("reflection", {})
        if reflection:
            reflection_scores = reflection.get("reflection_scores", {})
            if reflection_scores:
                output.append(f"\n{'─'*80}")
                output.append("反思评分:")
                for name, score in reflection_scores.items():
                    output.append(f"  {name}: {score:.2f}")

        output.append(f"\n{'='*80}\n")

        return "\n".join(output)

    async def run_once(self,
                       stream_name: str = "final_events",
                       read_history: bool = False) -> Optional[Dict]:
        """运行一次分析（读取一个事件并分析）"""
        # 读取事件
        event_data = await self.read_event_from_stream(stream_name, read_history=read_history)

        if not event_data:
            if read_history:
                print(f"⚠️  流 {stream_name} 中没有历史数据")
            else:
                print(f"⚠️  未读取到新事件（流: {stream_name}）")
                print(f"   提示: 使用 --history 参数可以读取历史数据")
            return None

        print(f"\n📥 读取到事件:")
        print(f"   事件ID: {event_data.get('event_id')}")
        print(f"   事件类型: {event_data.get('event_type')}")
        print(f"   交易对: {event_data.get('symbol')}")
        print(f"   事件级别: {event_data.get('event_level')}")

        # 转换为 EventSignal
        event_signal = self.map_event_to_signal(event_data)

        # 分析事件
        result = await self.analyze_event(event_signal)

        # 添加原始事件信息
        result["original_event"] = event_data

        return result

    async def run_continuous(self,
                             stream_name: str = "final_events",
                             interval: int = 10,
                             read_history: bool = False):
        """持续运行分析"""
        print(f"\n{'='*80}")
        print(f"启动持续分析模式")
        print(f"监听流: {stream_name}")
        print(f"检查间隔: {interval} 秒")
        print(f"按 Ctrl+C 停止")
        print(f"{'='*80}\n")

        first_run = True
        try:
            while True:
                # 第一次运行且指定了 --history，则读取历史；否则只读新消息
                use_history = read_history and first_run
                result = await self.run_once(stream_name, read_history=use_history)
                first_run = False

                if result:
                    # 格式化并打印结果
                    formatted = self.format_result(result)
                    print(formatted)

                    # 保存结果到文件（可选）
                    await self.save_result(result)
                else:
                    print(f"等待新事件... (每 {interval} 秒检查一次)")

                await asyncio.sleep(interval)

        except KeyboardInterrupt:
            print(f"\n\n停止分析")
        except Exception as e:
            print(f"\n❌ 运行错误: {e}")
            import traceback
            traceback.print_exc()

    async def save_result(self, result: Dict):
        """保存结果到文件"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analysis_result_{timestamp}.json"

            # 确保 results 目录存在
            results_dir = os.path.join(project_root, "results")
            os.makedirs(results_dir, exist_ok=True)

            filepath = os.path.join(results_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            print(f"💾 结果已保存: {filepath}")

        except Exception as e:
            print(f"⚠️  保存结果失败: {e}")

    async def close(self):
        """关闭连接"""
        if self.redis:
            await self.redis.aclose()


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="AI 分析脚本")
    parser.add_argument(
        "--stream",
        type=str,
        default="final_events",
        choices=["raw_event_stream", "l0_events", "l1_events", "final_events"],
        help="要监听的事件流（默认: final_events）")
    parser.add_argument("--mode",
                        type=str,
                        default="once",
                        choices=["once", "continuous"],
                        help="运行模式: once=运行一次, continuous=持续运行（默认: once）")
    parser.add_argument("--interval",
                        type=int,
                        default=10,
                        help="持续模式下的检查间隔（秒，默认: 10）")
    parser.add_argument("--history",
                        action="store_true",
                        help="读取历史数据（从最新的一条开始），而不是只读新消息")

    args = parser.parse_args()

    analyzer = AIAnalyzer()

    try:
        # 连接 Redis
        if not await analyzer.connect_redis():
            return

        # 运行分析
        if args.mode == "once":
            result = await analyzer.run_once(args.stream, read_history=args.history)

            if result:
                formatted = analyzer.format_result(result)
                print(formatted)
                await analyzer.save_result(result)
            else:
                print("未读取到事件")
        else:
            # 持续模式：第一次读取历史，后续读取新消息
            if args.history:
                print("⚠️  持续模式下，--history 参数只在第一次有效，后续会读取新消息")
            await analyzer.run_continuous(args.stream, args.interval, read_history=args.history)

    finally:
        await analyzer.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n程序已停止")
