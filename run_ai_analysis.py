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
from typing import Dict, Any, Optional, List

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agent_server.events import EventSignal
from agent_server.runtime import handle_event
from agent_server.utils.multi_timeframe_analyzer import MultiTimeframeAnalyzer
import redis.asyncio as aioredis


class AIAnalyzer:

    def __init__(self, symbol_filter: Optional[str] = None):
        # Redis 配置（从环境变量读取）
        self.symbol_filter = symbol_filter.upper() if symbol_filter else None  # 币种过滤器（转换为大写）
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

        # 多时间维度分析器
        self.multi_timeframe_analyzer = MultiTimeframeAnalyzer(
            redis_host=self.redis_host,
            redis_port=self.redis_port,
            redis_password=self.redis_password,
            redis_db=self.redis_db
        )

    async def connect_redis(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        连接 Redis（带重试机制）
        
        Args:
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        
        Returns:
            bool: 连接是否成功
        """
        # 如果已有连接，先检查是否健康
        if self.redis:
            try:
                await self.redis.ping()
                return True
            except:
                # 连接已断开，关闭旧连接
                try:
                    await self.redis.aclose()
                except:
                    pass
                self.redis = None
        
        # 尝试连接（带重试）
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                # 创建新连接
                self.redis = aioredis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    password=self.redis_password,
                    db=self.redis_db,
                    decode_responses=True,
                    socket_connect_timeout=3,  # 连接超时3秒
                    socket_timeout=3,  # 操作超时3秒
                    retry_on_timeout=True,
                    health_check_interval=30,
                    socket_keepalive=True,
                    socket_keepalive_options={}
                )
                
                # 探测连接（快速ping）
                await asyncio.wait_for(self.redis.ping(), timeout=2.0)
                
                print(
                    f"✅ Redis 连接成功: {self.redis_host}:{self.redis_port}/{self.redis_db}"
                )
                return True
                
            except asyncio.TimeoutError:
                last_error = "连接超时"
                if attempt < max_retries:
                    print(f"⚠️  Redis 连接超时，{retry_delay}秒后重试 ({attempt}/{max_retries})...")
                    await asyncio.sleep(retry_delay)
                else:
                    print(f"❌ Redis 连接失败: {last_error} (已重试 {max_retries} 次)")
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    print(f"⚠️  Redis 连接失败: {e}，{retry_delay}秒后重试 ({attempt}/{max_retries})...")
                    await asyncio.sleep(retry_delay)
                else:
                    print(f"❌ Redis 连接失败: {last_error} (已重试 {max_retries} 次)")
            
            # 清理失败的连接
            if self.redis:
                try:
                    await self.redis.aclose()
                except:
                    pass
                self.redis = None
        
        # 所有重试都失败，返回False但不抛出异常
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
                # 先检查流是否有数据
                stream_length = await self.redis.xlen(stream_name)
                if stream_length == 0:
                    return None
                
                # 读取历史消息（从最新开始倒序）
                # 如果指定了币种过滤，读取更多消息以便过滤
                read_count = count if not self.symbol_filter else min(100, stream_length)
                
                messages = await self.redis.xrevrange(
                    stream_name,
                    max="+",  # 从最新开始
                    min="-",  # 到最旧
                    count=read_count
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

            # 如果指定了币种过滤，检查是否匹配
            if self.symbol_filter:
                event_symbol = event_data.get("symbol", "").upper()
                if event_symbol != self.symbol_filter:
                    # 不匹配，跳过这条事件
                    if read_history:
                        # 历史模式下，从已读取的消息列表中查找匹配的币种
                        # 如果第一次读取了多条消息，先在这些消息中查找
                        if len(messages) > 1:
                            for msg_entry_id, msg_fields in messages[1:]:
                                msg_event_data = dict(msg_fields)
                                # 解析 payload
                                if "payload" in msg_event_data:
                                    try:
                                        msg_event_data["payload"] = json.loads(msg_event_data["payload"])
                                    except:
                                        pass
                                # 检查币种
                                msg_symbol = msg_event_data.get("symbol", "").upper()
                                if msg_symbol == self.symbol_filter:
                                    self.stream_offsets[stream_name] = msg_entry_id
                                    return msg_event_data
                        
                        # 如果已读取的消息中没有匹配的，继续读取更多历史消息
                        max_attempts = 100
                        attempts = 0
                        last_entry_id = entry_id
                        checked_count = 0
                        
                        while attempts < max_attempts:
                            attempts += 1
                            # 读取更多历史消息（从当前条目的前一条开始）
                            more_messages = await self.redis.xrevrange(
                                stream_name,
                                max=last_entry_id,  # 从当前条目的前一条开始（不包含当前）
                                min="-",
                                count=100  # 每次读取100条以提高效率
                            )
                            
                            if not more_messages or len(more_messages) == 0:
                                # 没有更多消息了
                                if checked_count > 0:
                                    print(f"⚠️  已检查 {checked_count} 条消息，未找到币种 {self.symbol_filter} 的事件")
                                return None
                            
                            # 遍历读取到的消息，查找匹配的币种
                            for msg_entry_id, msg_fields in more_messages:
                                checked_count += 1
                                msg_event_data = dict(msg_fields)
                                
                                # 解析 payload
                                if "payload" in msg_event_data:
                                    try:
                                        msg_event_data["payload"] = json.loads(msg_event_data["payload"])
                                    except:
                                        pass
                                
                                # 检查币种
                                msg_symbol = msg_event_data.get("symbol", "").upper()
                                if msg_symbol == self.symbol_filter:
                                    self.stream_offsets[stream_name] = msg_entry_id
                                    if checked_count > 1:
                                        print(f"✅ 在检查了 {checked_count} 条消息后，找到币种 {self.symbol_filter} 的事件")
                                    return msg_event_data
                            
                            # 更新 last_entry_id 为最后一条消息的 entry_id（继续向前读取）
                            last_entry_id = more_messages[-1][0]
                        
                        # 尝试次数过多，返回 None
                        print(f"⚠️  已检查 {checked_count} 条消息，未找到币种 {self.symbol_filter} 的事件")
                        return None
                    else:
                        # 实时模式下，返回 None，等待下一条
                        return None

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

        # 检查是否是多时间维度结果
        if result.get("multi_timeframe") or "analysis_by_timeframe" in result:
            return self._format_multi_timeframe_result(result)

        # 单事件结果（原有逻辑）
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

    def _format_multi_timeframe_result(self, result: Dict) -> str:
        """格式化多时间维度分析结果（中文输出）"""
        output = []
        output.append(f"\n{'='*80}")
        output.append(f"多时间维度 AI 分析结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append(f"{'='*80}\n")
        
        symbol = result.get("symbol", "UNKNOWN")
        base_event = result.get("base_event", {})
        analysis_by_timeframe = result.get("analysis_by_timeframe", {})
        
        output.append(f"📊 交易对: {symbol}\n")
        output.append(f"📌 基础事件: {base_event.get('event_id', 'N/A')}\n")
        output.append(f"⏱️  找到的时间维度: {', '.join(result.get('found_timeframes', []))}\n")
        output.append(f"\n{'='*80}\n")
        
        # 显示各时间维度的分析结果
        for timeframe, analysis_result in analysis_by_timeframe.items():
            if "error" in analysis_result:
                output.append(f"\n{'─'*80}")
                output.append(f"⏱️  时间维度: {timeframe} - ❌ 分析失败")
                output.append(f"   错误: {analysis_result.get('error')}")
                continue
            
            output.append(f"\n{'─'*80}")
            output.append(f"⏱️  时间维度: {timeframe}")
            output.append(f"{'─'*80}")
            
            names = analysis_result.get("names", [])
            outputs = analysis_result.get("outputs", [])
            
            for name, output_str in zip(names, outputs):
                agent_name_map = {
                    "technical": "技术分析",
                    "risk": "风险评估",
                    "news": "新闻分析",
                    "portfolio": "投资组合",
                    "trading_decision": "交易决策"
                }
                agent_name_cn = agent_name_map.get(name, name)
                output.append(f"\n🤖 {agent_name_cn} Agent ({timeframe}):")
                try:
                    output_obj = json.loads(output_str)
                    # 提取关键信息并中文显示
                    if isinstance(output_obj, dict):
                        content = output_obj.get("content", {})
                        if isinstance(content, dict):
                            summary = content.get("summary", "")
                            details = content.get("details", "")
                            confidence = output_obj.get("confidence", 0.0)
                            
                            output.append(f"   置信度: {confidence:.2%}")
                            if summary:
                                output.append(f"   摘要: {summary[:200]}")
                            if details:
                                output.append(f"   详情: {details[:300]}")
                        else:
                            output.append(f"   {json.dumps(output_obj, indent=2, ensure_ascii=False)[:500]}")
                    else:
                        output.append(f"   {json.dumps(output_obj, indent=2, ensure_ascii=False)[:500]}")
                except:
                    output.append(f"   {str(output_str)[:500]}")
                output.append("")
            
            # 显示该时间维度的交易决策
            timeframe_decision = analysis_result.get("trading_decision", {})
            if timeframe_decision:
                action = timeframe_decision.get("action", "hold")
                confidence = timeframe_decision.get("confidence", 0.0)
                rationale = timeframe_decision.get("rationale", "")
                action_map = {
                    "open": "开仓",
                    "close": "平仓",
                    "hold": "保持不动"
                }
                action_cn = action_map.get(action, action)
                output.append(f"   💡 该时间维度决策: {action_cn} (置信度: {confidence:.2%})")
                if rationale:
                    output.append(f"      理由: {rationale[:150]}")
        
        # 显示最终交易决策
        trading_decision = result.get("trading_decision")
        if trading_decision:
            output.append(f"\n{'='*80}")
            output.append("🎯 最终交易决策")
            output.append(f"{'='*80}")
            
            action = trading_decision.get("action", "hold")
            confidence = trading_decision.get("confidence", 0.0)
            rationale = trading_decision.get("rationale", "")
            risk_level = trading_decision.get("risk_level", "medium")
            
            action_map = {
                "open": "开仓",
                "close": "平仓", 
                "hold": "保持不动"
            }
            risk_map = {
                "low": "低风险",
                "medium": "中等风险",
                "high": "高风险"
            }
            
            output.append(f"操作: {action_map.get(action, action)}")
            output.append(f"置信度: {confidence:.2%}")
            output.append(f"风险等级: {risk_map.get(risk_level, risk_level)}")
            
            if action in ("open", "close"):
                position_side = trading_decision.get("positionSide", "")
                side = trading_decision.get("side", "")
                leverage = trading_decision.get("leverage", 0)
                sums = trading_decision.get("sums", "0")
                open_avg_px = trading_decision.get("openAvgPx", 0)
                stop_loss = trading_decision.get("stop_loss")
                take_profit = trading_decision.get("take_profit")
                
                position_map = {
                    "LONG": "做多",
                    "SHORT": "做空"
                }
                side_map = {
                    "BUY": "买入",
                    "SELL": "卖出"
                }
                
                output.append(f"方向: {position_map.get(position_side, position_side)} ({side_map.get(side, side)})")
                output.append(f"杠杆: {leverage}x")
                output.append(f"数量: {sums}")
                output.append(f"开仓价格: {open_avg_px:,.2f}")
                if stop_loss:
                    output.append(f"止损价格: {stop_loss:,.2f}")
                if take_profit:
                    output.append(f"止盈价格: {take_profit:,.2f}")
            
            if rationale:
                output.append(f"\n决策理由:")
                output.append(f"  {rationale}")
        
        output.append(f"\n{'='*80}\n")
        
        return "\n".join(output)

    async def run_direct_from_indicators(
        self,
        symbol: str,
        timestamp_ms: Optional[int] = None,
        timeframes: List[str] = None
    ) -> Optional[Dict]:
        """
        直接从指标数据进行分析（不需要事件流）
        
        Args:
            symbol: 交易对（如 BTCUSDT）
            timestamp_ms: 时间戳（毫秒），None表示使用当前时间
            timeframes: 时间维度列表，默认 ["1m", "5m", "15m", "1h"]
        """
        if timeframes is None:
            timeframes = ["1m", "5m", "15m", "1h"]
        
        if timestamp_ms is None:
            import time
            timestamp_ms = int(time.time() * 1000)
        
        print(f"\n📊 直接基于指标数据进行分析:")
        print(f"   交易对: {symbol}")
        print(f"   时间戳: {timestamp_ms}")
        print(f"   时间维度: {', '.join(timeframes)}")
        
        # 连接多时间维度分析器的 Redis
        if not self.multi_timeframe_analyzer.redis:
            await self.multi_timeframe_analyzer.connect_redis()
        
        # 创建基础事件（用于触发分析）
        base_event = {
            "event_id": f"{symbol}.direct.indicators.{timestamp_ms}",
            "symbol": symbol,
            "event_type": "direct_indicators",
            "event_level": "2",
            "timestamp": str(timestamp_ms),
            "source": "direct_indicators"
        }
        
        # 进行多时间维度分析（使用指标数据）
        result = await self.multi_timeframe_analyzer.analyze_multi_timeframe(
            symbol=symbol,
            base_event=base_event,
            timeframes=timeframes,
            use_indicators_direct=True  # 强制使用指标数据
        )
        
        # 添加基础事件信息
        result["original_event"] = base_event
        result["analysis_mode"] = "direct_indicators"
        
        return result
    
    async def run_once(self,
                       stream_name: str = "final_events",
                       read_history: bool = False,
                       use_multi_timeframe: bool = True) -> Optional[Dict]:
        """
        运行一次分析（读取一个事件并分析）
        
        Args:
            stream_name: 事件流名称
            read_history: 是否读取历史数据
            use_multi_timeframe: 是否使用多时间维度分析（默认True）
        """
        # 读取事件
        event_data = await self.read_event_from_stream(stream_name, read_history=read_history)

        if not event_data:
            if read_history:
                # 检查流是否有数据
                try:
                    stream_length = await self.redis.xlen(stream_name)
                    if stream_length == 0:
                        print(f"⚠️  流 {stream_name} 中没有数据（流长度为 0）")
                    elif self.symbol_filter:
                        print(f"⚠️  流 {stream_name} 中有 {stream_length} 条消息，但没有找到币种 {self.symbol_filter} 的事件")
                    else:
                        print(f"⚠️  流 {stream_name} 中没有历史数据（流长度为 {stream_length}，但读取失败）")
                except Exception as e:
                    print(f"⚠️  流 {stream_name} 中没有历史数据（检查流长度时出错: {e}）")
            else:
                print(f"⚠️  未读取到新事件（流: {stream_name}）")
                print(f"   提示: 使用 --history 参数可以读取历史数据")
            return None

        print(f"\n📥 读取到事件:")
        print(f"   事件ID: {event_data.get('event_id')}")
        print(f"   事件类型: {event_data.get('event_type')}")
        print(f"   交易对: {event_data.get('symbol')}")
        print(f"   事件级别: {event_data.get('event_level')}")
        if self.symbol_filter:
            print(f"   🔍 币种过滤: {self.symbol_filter}")

        # 如果启用多时间维度分析
        if use_multi_timeframe:
            symbol = event_data.get('symbol', 'BTCUSDT')
            
            # 连接多时间维度分析器的 Redis
            if not self.multi_timeframe_analyzer.redis:
                await self.multi_timeframe_analyzer.connect_redis()
            
            # 进行多时间维度分析
            # 根据参数选择使用指标数据还是事件流查找
            use_indicators = not getattr(self, '_use_events', False)
            result = await self.multi_timeframe_analyzer.analyze_multi_timeframe(
                symbol=symbol,
                base_event=event_data,
                timeframes=["1m", "5m", "15m", "1h"],  # 默认4个时间维度，包含1h
                use_indicators_direct=use_indicators  # True=指标数据，False=事件流查找
            )
            
            # 添加原始事件信息
            result["original_event"] = event_data
            
            return result
        else:
            # 单事件分析（原有逻辑）
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
                             read_history: bool = False,
                             use_multi_timeframe: bool = True):
        """持续运行分析"""
        print(f"\n{'='*80}")
        print(f"启动持续分析模式")
        print(f"监听流: {stream_name}")
        print(f"检查间隔: {interval} 秒")
        print(f"多时间维度分析: {'启用' if use_multi_timeframe else '禁用'}")
        if use_multi_timeframe:
            use_indicators = not getattr(self, '_use_events', False)
            print(f"数据来源: {'指标数据（快速验证）' if use_indicators else '事件流（突破/大变动）'}")
        if self.symbol_filter:
            print(f"币种过滤: {self.symbol_filter} (只分析此币种)")
        print(f"按 Ctrl+C 停止")
        print(f"{'='*80}\n")

        first_run = True
        try:
            while True:
                # 第一次运行且指定了 --history，则读取历史；否则只读新消息
                use_history = read_history and first_run
                result = await self.run_once(
                    stream_name, 
                    read_history=use_history,
                    use_multi_timeframe=use_multi_timeframe
                )
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
        await self.multi_timeframe_analyzer.close()


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
    parser.add_argument("--single-timeframe",
                        action="store_true",
                        help="禁用多时间维度分析，使用单一事件分析（默认启用多时间维度）")
    parser.add_argument("--use-events",
                        action="store_true",
                        help="使用事件流查找多时间维度（默认使用指标数据），适合分析突破/大变动事件")
    parser.add_argument("--direct",
                        action="store_true",
                        help="直接从指标数据分析，不需要事件流（需要指定 --symbol）")
    parser.add_argument("--timestamp",
                        type=int,
                        default=None,
                        help="指定时间戳（毫秒），用于 --direct 模式，不指定则使用当前时间")
    parser.add_argument("--symbol",
                        type=str,
                        default=None,
                        help="只分析指定币种（如：BTCUSDT, ETHUSDT），不指定则分析所有币种")

    args = parser.parse_args()

    # 直接基于指标数据分析模式
    if args.direct:
        if not args.symbol:
            print("❌ 错误: --direct 模式需要指定 --symbol 参数")
            print("   示例: python run_ai_analysis.py --direct --symbol BTCUSDT")
            return
        
        analyzer = AIAnalyzer(symbol_filter=args.symbol)
        
        try:
            # 连接 Redis
            if not await analyzer.connect_redis():
                return
            
            # 直接基于指标数据分析
            result = await analyzer.run_direct_from_indicators(
                symbol=args.symbol,
                timestamp_ms=args.timestamp,
                timeframes=["1m", "5m", "15m", "1h"]
            )
            
            if result:
                formatted = analyzer.format_result(result)
                print(formatted)
                await analyzer.save_result(result)
            else:
                print("❌ 分析失败")
        
        finally:
            await analyzer.close()
        return

    # 创建分析器（支持币种过滤）
    analyzer = AIAnalyzer(symbol_filter=args.symbol)
    
    # 设置是否使用事件流查找
    analyzer._use_events = args.use_events

    try:
        # 连接 Redis
        if not await analyzer.connect_redis():
            return

        # 运行分析
        use_multi_timeframe = not args.single_timeframe
        
        if args.mode == "once":
            result = await analyzer.run_once(
                args.stream, 
                read_history=args.history,
                use_multi_timeframe=use_multi_timeframe
            )

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
            await analyzer.run_continuous(
                args.stream, 
                args.interval, 
                read_history=args.history,
                use_multi_timeframe=use_multi_timeframe
            )

    finally:
        await analyzer.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n程序已停止")
