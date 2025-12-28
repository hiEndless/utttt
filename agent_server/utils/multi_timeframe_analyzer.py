"""
多时间维度分析模块
从 Redis 获取多个时间维度的事件，进行综合分析
"""
import asyncio
import json
import time
from typing import Dict, List, Optional, Any
import redis.asyncio as aioredis
from agent_server.events import EventSignal
from agent_server.runtime import handle_event


class MultiTimeframeAnalyzer:
    """多时间维度分析器"""

    # 支持的时间维度（按优先级排序）
    TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]

    # 时间维度对应的秒数
    TIMEFRAME_SECONDS = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "2h": 7200,
        "4h": 14400,
        "1d": 86400
    }

    def __init__(self, redis_host: str, redis_port: int, redis_password: str,
                 redis_db: int):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.redis_db = redis_db
        self.redis: Optional[aioredis.Redis] = None

    async def connect_redis(self,
                            max_retries: int = 3,
                            retry_delay: float = 1.0):
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
                    socket_keepalive_options={})

                # 探测连接（快速ping）
                await asyncio.wait_for(self.redis.ping(), timeout=2.0)

                print(
                    f"✅ Redis 连接成功: {self.redis_host}:{self.redis_port}/{self.redis_db}"
                )
                return True

            except asyncio.TimeoutError:
                last_error = "连接超时"
                if attempt < max_retries:
                    print(
                        f"⚠️  Redis 连接超时，{retry_delay}秒后重试 ({attempt}/{max_retries})..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    print(f"❌ Redis 连接失败: {last_error} (已重试 {max_retries} 次)")
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    print(
                        f"⚠️  Redis 连接失败: {e}，{retry_delay}秒后重试 ({attempt}/{max_retries})..."
                    )
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

    async def get_events_by_timeframe(
            self,
            symbol: str,
            base_timestamp_ms: int,
            timeframes: List[str] = None,
            max_age_minutes: int = 30) -> Dict[str, Optional[Dict]]:
        """
        获取指定交易对在多个时间维度的事件
        
        Args:
            symbol: 交易对（如 BTCUSDT）
            base_timestamp_ms: 基准时间戳（毫秒）
            timeframes: 时间维度列表，默认 ["1m", "5m", "15m"]
            max_age_minutes: 最大时间跨度（分钟），默认30分钟
        
        Returns:
            Dict[timeframe, event_data] - 每个时间维度对应的事件数据
        """
        if timeframes is None:
            timeframes = ["1m", "5m", "15m"]  # 默认3个时间维度

        # 确保Redis连接健康
        if not self.redis:
            await self.connect_redis()
        else:
            # 检查连接是否健康
            try:
                await self.redis.ping()
            except:
                # 连接已断开，重新连接
                await self.connect_redis()

        max_age_ms = max_age_minutes * 60 * 1000
        min_timestamp_ms = base_timestamp_ms - max_age_ms

        events_by_timeframe = {}

        # 从各个事件流中查找对应时间维度的事件
        streams = [
            "final_events", "l1_events", "l0_events", "raw_event_stream"
        ]

        for timeframe in timeframes:
            events_by_timeframe[timeframe] = None

            # 构建事件类型模式
            event_patterns = [
                f"combo.{timeframe}.",
                f"{timeframe}.",
            ]

            # 从各个流中查找
            for stream_name in streams:
                try:
                    # 读取最近的事件（最多1000条）
                    messages = await self.redis.xrevrange(stream_name,
                                                          max="+",
                                                          min="-",
                                                          count=1000)

                    # 查找匹配的事件
                    for entry_id, fields in messages:
                        event_data = dict(fields)

                        # 检查交易对
                        if event_data.get("symbol") != symbol:
                            continue

                        # 检查时间戳
                        event_timestamp = event_data.get("timestamp")
                        if event_timestamp:
                            try:
                                event_ts_ms = int(event_timestamp)
                                if event_ts_ms < min_timestamp_ms or event_ts_ms > base_timestamp_ms:
                                    continue
                            except (ValueError, TypeError):
                                continue

                        # 检查事件类型是否匹配时间维度
                        event_type = event_data.get("event_type", "")
                        matches_timeframe = False
                        for pattern in event_patterns:
                            if pattern in event_type:
                                matches_timeframe = True
                                break

                        if matches_timeframe:
                            # 解析 payload
                            if "payload" in event_data:
                                try:
                                    event_data["payload"] = json.loads(
                                        event_data["payload"])
                                except:
                                    pass

                            events_by_timeframe[timeframe] = event_data
                            print(
                                f"✅ 找到 {timeframe} 事件: {event_data.get('event_id')}"
                            )
                            break

                    if events_by_timeframe[timeframe]:
                        break

                except Exception as e:
                    print(f"⚠️  从 {stream_name} 读取 {timeframe} 事件失败: {e}")
                    continue

        return events_by_timeframe

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
            "event_id": event_data.get("event_id"),
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

    async def analyze_multi_timeframe(
            self,
            symbol: str,
            base_event: Dict,
            timeframes: List[str] = None,
            use_indicators_direct: bool = True) -> Dict[str, Any]:
        """
        分析多个时间维度的事件
        
        Args:
            symbol: 交易对
            base_event: 基础事件（触发分析的事件）
            timeframes: 时间维度列表
            use_indicators_direct: True=使用指标数据（推荐），False=使用事件流查找
        
        Returns:
            包含所有时间维度分析结果的字典
        """
        if timeframes is None:
            timeframes = ["1m", "5m", "15m", "1h"]  # 默认包含1h

        # 优先使用指标数据（推荐方案）
        if use_indicators_direct:
            return await self.analyze_multi_timeframe_from_indicators(
                symbol=symbol, base_event=base_event, timeframes=timeframes)

        # 使用事件流查找（原有方案，作为备选）
        # 获取基准时间戳
        base_timestamp = base_event.get("timestamp")
        if base_timestamp:
            try:
                base_timestamp_ms = int(base_timestamp)
            except (ValueError, TypeError):
                base_timestamp_ms = int(time.time() * 1000)
        else:
            base_timestamp_ms = int(time.time() * 1000)

        # 获取各时间维度的事件
        print(f"\n🔍 获取 {symbol} 的多时间维度事件...")
        events_by_timeframe = await self.get_events_by_timeframe(
            symbol=symbol,
            base_timestamp_ms=base_timestamp_ms,
            timeframes=timeframes,
            max_age_minutes=30)

        # 统计找到的事件
        found_count = sum(1 for v in events_by_timeframe.values()
                          if v is not None)
        print(f"📊 找到 {found_count}/{len(timeframes)} 个时间维度的事件")

        # 定义单个时间维度的分析任务（用于并发执行）
        async def analyze_single_timeframe_event(
                timeframe: str, event_data: Optional[Dict]) -> tuple:
            """分析单个时间维度的事件（带超时控制）"""
            if event_data is None:
                return (timeframe, {
                    "timeframe": timeframe,
                    "error": "事件数据不存在"
                })

            # 根据时间维度设置不同的超时时间
            timeout_map = {
                "1m": 15,
                "5m": 20,
                "15m": 25,
                "30m": 30,
                "1h": 40,  # 1h数据量大，给更多时间
                "2h": 45,
                "4h": 50,
                "1d": 60
            }
            timeout = timeout_map.get(timeframe, 30)

            try:
                print(f"📈 开始分析 {timeframe} 时间维度（超时: {timeout}秒）...")
                start_time = time.time()

                # 标记这是中间分析，不应该执行交易推送
                event_data["_is_intermediate_analysis"] = True
                event_data["_timeframe"] = timeframe

                # 转换为 EventSignal
                event_signal = self.map_event_to_signal(event_data)

                # 调用 Agent 系统分析（带超时控制）
                try:
                    result = await asyncio.wait_for(handle_event(event_signal),
                                                    timeout=timeout)
                except asyncio.TimeoutError:
                    elapsed = time.time() - start_time
                    print(f"⏱️  {timeframe} 分析超时（{elapsed:.1f}秒 > {timeout}秒）")
                    result = {
                        "names": ["technical", "risk"],
                        "outputs": [],
                        "scores": {},
                        "reflection": {
                            "mode": "default",
                            "reflection_scores": {},
                            "notes": []
                        },
                        "fusion": "",
                        "weights": {},
                        "trading_decision": {
                            "action": "hold",
                            "symbol": symbol,
                            "confidence": 0.0,
                            "rationale": f"{timeframe} 周期分析超时",
                            "risk_level": "medium"
                        },
                        "error": "timeout"
                    }

                # 添加时间维度信息
                result["timeframe"] = timeframe
                result["event_data"] = event_data

                elapsed = time.time() - start_time
                print(f"✅ {timeframe} 分析完成（耗时: {elapsed:.1f}秒）")
                return (timeframe, result)

            except Exception as e:
                elapsed = time.time() - start_time if 'start_time' in locals(
                ) else 0
                print(f"❌ {timeframe} 分析失败（耗时: {elapsed:.1f}秒）: {e}")
                import traceback
                traceback.print_exc()
                return (timeframe, {
                    "timeframe": timeframe,
                    "error": str(e),
                    "event_data": event_data
                })

        # 并发执行所有时间维度的分析
        print(f"\n🚀 并发分析 {found_count} 个时间维度...")
        tasks = []
        for timeframe, event_data in events_by_timeframe.items():
            if event_data is not None:
                task = analyze_single_timeframe_event(timeframe, event_data)
                tasks.append(task)

        # 等待所有分析任务完成（带进度监控）
        if tasks:
            print(f"⏳ 等待 {len(tasks)} 个分析任务完成...")
            start_time = time.time()

            results = await asyncio.gather(*tasks, return_exceptions=True)

            elapsed = time.time() - start_time
            print(f"⏱️  所有分析任务完成（总耗时: {elapsed:.1f}秒）")

            # 整理分析结果
            analysis_results = {}
            for result in results:
                if isinstance(result, Exception):
                    print(f"⚠️  分析任务异常: {result}")
                    continue
                timeframe, analysis_result = result
                analysis_results[timeframe] = analysis_result
        else:
            analysis_results = {}

        print(f"\n✅ 所有时间维度分析完成（共 {len(analysis_results)} 个）")

        # 验证所有并发分析都已完成
        expected_count = len([
            tf for tf, data in events_by_timeframe.items() if data is not None
        ])
        actual_count = len(analysis_results)
        if actual_count < expected_count:
            print(f"⚠️  警告: 期望 {expected_count} 个分析结果，但只得到 {actual_count} 个")
            print(
                f"   缺失的时间维度: {set(events_by_timeframe.keys()) - set(analysis_results.keys())}"
            )

        # 确保所有分析结果都包含必要的数据
        for timeframe, result in analysis_results.items():
            if "error" not in result and "names" not in result:
                print(f"⚠️  警告: {timeframe} 的分析结果不完整")

        # 步骤2: 整合所有时间维度的分析结果
        print(f"\n📊 步骤2: 整合所有分析结果...")
        integrated_result = {
            "symbol":
            symbol,
            "base_event":
            base_event,
            "timeframes":
            timeframes,
            "analysis_by_timeframe":
            analysis_results,
            "found_timeframes": [
                tf for tf, data in events_by_timeframe.items()
                if data is not None
            ],
            "timestamp":
            base_timestamp_ms,
            "data_source":
            "events"  # 标记数据来源
        }

        # 步骤3: 获取市场数据并进行综合分析
        print(f"\n📈 步骤3: 获取市场数据并进行综合分析...")
        market_data = await self._get_market_data(symbol)
        integrated_result["market_data"] = market_data
        print(f"✅ 市场数据获取完成:")
        print(f"   - 当前价格: {market_data.get('price', 'N/A')}")
        print(
            f"   - 多空比数据: {'已获取' if market_data.get('long_short_ratio') else '未获取'}"
        )
        print(
            f"   - 爆仓数据: {'已获取' if market_data.get('liquidation') else '未获取'}")
        print(
            f"   - 支撑阻力位: {'已获取' if market_data.get('support_resistance') else '未获取'}"
        )

        # 步骤4: 调用 Agent 系统进行最终决策（基于所有分析结果和市场数据）
        print(f"\n🎯 步骤4: 得出最终结论（基于 {actual_count} 个时间维度的完整结果 + 市场数据）...")
        # 注意：handle_event 已在文件顶部导入，这里直接使用
        final_result = await handle_event(integrated_result)

        # 合并结果
        final_result.update(integrated_result)

        return final_result

    async def get_indicators_by_timeframe(
            self,
            symbol: str,
            timeframes: List[str] = None,
            timestamp_ms: Optional[int] = None) -> Dict[str, Optional[Dict]]:
        """
        获取指定交易对在多个时间维度的指标数据（推荐方案）
        
        Args:
            symbol: 交易对（如 BTCUSDT）
            timeframes: 时间维度列表，默认 ["1m", "5m", "15m", "1h"]
            timestamp_ms: 时间戳（毫秒），None表示使用当前时间
        
        Returns:
            Dict[timeframe, indicators_data] - 每个时间维度对应的指标数据
        """
        if timeframes is None:
            timeframes = ["1m", "5m", "15m", "1h"]

        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)

        if not self.redis:
            await self.connect_redis()

        indicators_by_timeframe = {}

        for timeframe in timeframes:
            # 直接从Redis读取指标数据
            key = f"indicators:binance:{symbol}:{timeframe}"
            try:
                indicators_raw = await self.redis.get(key)
                if indicators_raw:
                    indicators = json.loads(indicators_raw)
                    indicators_by_timeframe[timeframe] = {
                        "indicators": indicators,
                        "timeframe": timeframe,
                        "timestamp": timestamp_ms,
                        "symbol": symbol
                    }
                    print(f"✅ 获取 {timeframe} 指标数据成功")
                else:
                    indicators_by_timeframe[timeframe] = None
                    print(f"⚠️  {timeframe} 指标数据不存在")
            except Exception as e:
                print(f"⚠️  读取 {timeframe} 指标失败: {e}")
                indicators_by_timeframe[timeframe] = None

        return indicators_by_timeframe

    async def create_event_from_indicators(self, symbol: str, timeframe: str,
                                           indicators: Dict,
                                           timestamp_ms: int) -> Dict:
        """
        基于指标数据创建事件对象
        
        Args:
            symbol: 交易对
            timeframe: 时间维度
            indicators: 指标数据
            timestamp_ms: 时间戳
        
        Returns:
            事件数据字典
        """
        # 从指标数据中提取关键信息
        # 尝试从指标中提取信号强度
        event_level = "2"  # 默认级别

        # 如果有RSI、KDJ等指标，可以根据数值判断级别
        rsi14 = indicators.get("rsi14")
        if rsi14 is not None:
            if rsi14 > 70 or rsi14 < 30:
                event_level = "3"  # 超买超卖，级别提高

        event_data = {
            "event_id": f"{symbol}.indicators.{timeframe}.{timestamp_ms}",
            "symbol": symbol,
            "event_type": f"indicators.{timeframe}",
            "event_level": event_level,
            "timestamp": str(timestamp_ms),
            "source": "indicators_direct",
            "payload": {
                "interval": timeframe,
                "indicators": indicators,
                "timestamp": timestamp_ms
            }
        }

        return event_data

    async def analyze_multi_timeframe_from_indicators(
            self,
            symbol: str,
            base_event: Optional[Dict] = None,
            timeframes: List[str] = None,
            timestamp_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        基于指标数据进行多时间维度分析（推荐方案）
        
        Args:
            symbol: 交易对
            base_event: 基础事件（可选，用于触发分析）
            timeframes: 时间维度列表
            timestamp_ms: 时间戳（可选，None表示使用当前时间）
        
        Returns:
            包含所有时间维度分析结果的字典
        """
        if timeframes is None:
            timeframes = ["1m", "5m", "15m", "1h"]

        if timestamp_ms is None:
            if base_event and base_event.get("timestamp"):
                timestamp_ms = int(base_event.get("timestamp"))
            else:
                timestamp_ms = int(time.time() * 1000)

        # 获取各时间维度的指标数据
        print(f"\n🔍 获取 {symbol} 的多时间维度指标数据（时间点: {timestamp_ms}）...")
        indicators_by_timeframe = await self.get_indicators_by_timeframe(
            symbol=symbol, timeframes=timeframes, timestamp_ms=timestamp_ms)

        # 统计找到的指标
        found_count = sum(1 for v in indicators_by_timeframe.values()
                          if v is not None)
        print(f"📊 找到 {found_count}/{len(timeframes)} 个时间维度的指标数据")

        # 步骤1: 格式化各时间维度的指标数据（跳过AI分析，直接格式化）
        print(f"\n📊 步骤1: 格式化各时间维度指标数据...")
        formatted_indicators_by_timeframe = {}

        for timeframe, indicators_data in indicators_by_timeframe.items():
            if indicators_data is None:
                print(f"⚠️  {timeframe} 指标数据不存在，跳过")
                continue

            # 格式化指标数据，提取关键指标值
            formatted = self._format_indicators_for_ai(
                timeframe=timeframe,
                indicators=indicators_data["indicators"],
                symbol=symbol,
                timestamp_ms=timestamp_ms)
            formatted_indicators_by_timeframe[timeframe] = formatted
            print(f"✅ {timeframe} 指标数据格式化完成")

        print(
            f"\n✅ 所有时间维度指标数据格式化完成（共 {len(formatted_indicators_by_timeframe)} 个）"
        )

        # 步骤2: 整合所有时间维度的指标数据
        print(f"\n📊 步骤2: 整合所有时间维度指标数据...")
        integrated_result = {
            "symbol":
            symbol,
            "base_event":
            base_event,
            "timeframes":
            timeframes,
            "indicators_by_timeframe":
            formatted_indicators_by_timeframe,  # 使用格式化后的指标数据
            "found_timeframes": [
                tf for tf, data in indicators_by_timeframe.items()
                if data is not None
            ],
            "timestamp":
            timestamp_ms,
            "data_source":
            "indicators_direct"  # 标记为直接指标分析
        }

        # 步骤3: 获取并清洗市场数据
        print(f"\n📈 步骤3: 获取并清洗市场数据...")
        raw_market_data = await self._get_market_data(symbol)
        # 清洗市场数据，提取关键影响因子
        cleaned_market_data = self._clean_market_data(raw_market_data, symbol)
        integrated_result["market_data"] = cleaned_market_data
        print(f"✅ 市场数据清洗完成:")
        print(f"   - 当前价格: {cleaned_market_data.get('current_price', 'N/A')}")
        print(
            f"   - 多空比: {cleaned_market_data.get('long_short_ratio_summary', 'N/A')}"
        )
        print(
            f"   - 爆仓情况: {cleaned_market_data.get('liquidation_summary', 'N/A')}"
        )
        print(
            f"   - 支撑阻力位: {cleaned_market_data.get('support_resistance_summary', 'N/A')}"
        )

        # 步骤4: 调用 Agent 系统进行最终决策（基于格式化指标数据 + 清洗后的市场数据）
        print(
            f"\n🎯 步骤4: 得出最终结论（基于 {len(formatted_indicators_by_timeframe)} 个时间维度的指标数据 + 市场数据）..."
        )
        final_result = await handle_event(integrated_result)

        # 合并结果
        final_result.update(integrated_result)

        # 确保trade_json已生成（在trading_decision中已处理）
        # 这里只是确保结果中包含trade_json
        if "trading_decision" in final_result and "trade_json" not in final_result.get(
                "trading_decision", {}):
            # 如果trading_decision中没有trade_json，尝试生成
            trading_decision = final_result.get("trading_decision", {})
            if trading_decision:
                try:
                    from agent_server.agents.experts.analysis.trading_decision import TradingDecisionExpert
                    expert = TradingDecisionExpert()
                    trade_json = await expert._generate_trade_json(
                        trading_decision, integrated_result)
                    trading_decision["trade_json"] = trade_json
                    final_result["trading_decision"] = trading_decision
                except Exception as e:
                    print(f"⚠️  补充生成trade_json失败: {e}")

        return final_result

    async def _get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        获取市场行情数据（多空比、爆仓、支撑位等）
        
        Args:
            symbol: 交易对（如 BTCUSDT）
        
        Returns:
            包含市场行情数据的字典
        """
        market_data = {
            "price": None,
            "long_short_ratio": {},
            "liquidation": {},
            "support_resistance": {},
            "funding_rate": None,
            "ticker_24h": {}
        }

        if not self.redis:
            await self.connect_redis()

        try:
            # 1. 获取当前价格
            try:
                price_key = f"price:binance:{symbol}"
                price_data = await self.redis.hgetall(price_key)
                if price_data and "price" in price_data:
                    market_data["price"] = float(price_data["price"])
                    market_data["bid_liquidity"] = float(
                        price_data.get("bid", 0))
                    market_data["ask_liquidity"] = float(
                        price_data.get("ask", 0))
            except Exception as e:
                print(f"⚠️  获取价格失败: {e}")

            # 2. 获取多空比数据（从 market_raw）
            try:
                from api.application.apps.indicators.market_raw_analysis import (
                    read_market_raw, build_participant_structure)
                raw_data = await read_market_raw("binance", symbol)
                participant_structure = build_participant_structure(
                    raw_data, symbol)

                market_data["long_short_ratio"] = participant_structure.get(
                    "participant_structure", {})
                market_data["funding_rate"] = participant_structure.get(
                    "funding_rate", {})
                market_data["ticker_24h"] = participant_structure.get(
                    "ticker", {})
                market_data["market_summary"] = participant_structure.get(
                    "summary", {})
            except Exception as e:
                print(f"⚠️  获取多空比数据失败: {e}")

            # 3. 获取爆仓数据
            try:
                # 尝试多个可能的键名
                possible_keys = [
                    f"force_stats:{symbol}", f"force_stats:binance:{symbol}",
                    f"liquidation:{symbol}", f"liquidation:binance:{symbol}"
                ]

                force_stats = None
                for key in possible_keys:
                    try:
                        force_stats = await self.redis.get(key)
                        if force_stats:
                            print(f"✅ 从 {key} 获取爆仓数据")
                            break
                    except:
                        continue

                if force_stats:
                    stats = json.loads(force_stats)
                    market_data["liquidation"] = {
                        "buy_count": stats.get("BUY", 0),
                        "sell_count": stats.get("SELL", 0),
                        "buy_qty": stats.get("BUY_QTY", 0.0),
                        "sell_qty": stats.get("SELL_QTY", 0.0),
                        "timestamp": stats.get("timestamp", 0)
                    }
                else:
                    print(f"⚠️  未找到爆仓数据，尝试的键: {possible_keys}")
            except Exception as e:
                print(f"⚠️  获取爆仓数据失败: {e}")
                import traceback
                traceback.print_exc()

            # 4. 从指标数据中提取支撑位和阻力位
            try:
                # 尝试从1m指标中获取支撑阻力位
                indicators_key = f"indicators:binance:{symbol}:1m"
                indicators_raw = await self.redis.get(indicators_key)
                if indicators_raw:
                    indicators = json.loads(indicators_raw)
                    sr = indicators.get("sr", {})
                    if sr:
                        market_data["support_resistance"] = {
                            "R1": sr.get("R1"),
                            "R2": sr.get("R2"),
                            "R3": sr.get("R3"),
                            "S1": sr.get("S1"),
                            "S2": sr.get("S2"),
                            "S3": sr.get("S3")
                        }
            except Exception as e:
                print(f"⚠️  获取支撑阻力位失败: {e}")

        except Exception as e:
            print(f"⚠️  获取市场数据失败: {e}")

        return market_data

    def _format_indicators_for_ai(self, timeframe: str, indicators: Dict,
                                  symbol: str,
                                  timestamp_ms: int) -> Dict[str, Any]:
        """
        格式化指标数据，提取关键指标值，便于AI理解
        
        Args:
            timeframe: 时间维度
            indicators: 原始指标数据
            symbol: 交易对
            timestamp_ms: 时间戳
        
        Returns:
            格式化后的指标数据字典
        """
        formatted = {
            "timeframe": timeframe,
            "symbol": symbol,
            "timestamp": timestamp_ms,
            "price_info": {},
            "trend_indicators": {},
            "momentum_indicators": {},
            "volatility_indicators": {},
            "volume_indicators": {},
            "support_resistance": {},
            "signal_summary": {}
        }

        # 1. 价格信息
        if "close" in indicators:
            formatted["price_info"]["close"] = float(indicators["close"])
        if "open" in indicators:
            formatted["price_info"]["open"] = float(indicators["open"])
        if "high" in indicators:
            formatted["price_info"]["high"] = float(indicators["high"])
        if "low" in indicators:
            formatted["price_info"]["low"] = float(indicators["low"])

        # 计算价格变化
        if "close" in indicators and "open" in indicators:
            price_change = float(indicators["close"]) - float(
                indicators["open"])
            price_change_pct = (price_change / float(indicators["open"])) * 100
            formatted["price_info"]["change"] = price_change
            formatted["price_info"]["change_pct"] = round(price_change_pct, 2)

        # 2. 趋势指标 (MA, EMA, MACD)
        if "ema" in indicators:
            ema = indicators["ema"]
            if isinstance(ema, dict):
                formatted["trend_indicators"]["ema_20"] = ema.get("ema20")
                formatted["trend_indicators"]["ema_50"] = ema.get("ema50")
                formatted["trend_indicators"]["ema_200"] = ema.get("ema200")

        if "ma" in indicators:
            ma = indicators["ma"]
            if isinstance(ma, dict):
                formatted["trend_indicators"]["ma_20"] = ma.get("ma20")
                formatted["trend_indicators"]["ma_50"] = ma.get("ma50")
                formatted["trend_indicators"]["ma_200"] = ma.get("ma200")

        if "macd" in indicators:
            macd = indicators["macd"]
            if isinstance(macd, dict):
                formatted["trend_indicators"]["macd"] = macd.get("macd")
                formatted["trend_indicators"]["macd_signal"] = macd.get(
                    "signal")
                formatted["trend_indicators"]["macd_hist"] = macd.get("hist")
                # MACD信号判断
                if macd.get("macd") and macd.get("signal"):
                    if macd.get("macd") > macd.get("signal"):
                        formatted["trend_indicators"][
                            "macd_signal_direction"] = "bullish"
                    else:
                        formatted["trend_indicators"][
                            "macd_signal_direction"] = "bearish"

        # 3. 动量指标 (RSI, KDJ, ADX)
        if "rsi14" in indicators:
            rsi = float(indicators["rsi14"])
            formatted["momentum_indicators"]["rsi14"] = round(rsi, 2)
            # RSI信号判断
            if rsi > 70:
                formatted["momentum_indicators"]["rsi_signal"] = "overbought"
            elif rsi < 30:
                formatted["momentum_indicators"]["rsi_signal"] = "oversold"
            else:
                formatted["momentum_indicators"]["rsi_signal"] = "neutral"

        if "kdj" in indicators:
            kdj = indicators["kdj"]
            if isinstance(kdj, dict):
                formatted["momentum_indicators"]["k"] = kdj.get("k")
                formatted["momentum_indicators"]["d"] = kdj.get("d")
                formatted["momentum_indicators"]["j"] = kdj.get("j")
                # KDJ信号判断
                k_val = kdj.get("k", 50)
                d_val = kdj.get("d", 50)
                if k_val > d_val and k_val > 50:
                    formatted["momentum_indicators"]["kdj_signal"] = "bullish"
                elif k_val < d_val and k_val < 50:
                    formatted["momentum_indicators"]["kdj_signal"] = "bearish"
                else:
                    formatted["momentum_indicators"]["kdj_signal"] = "neutral"

        if "adx" in indicators:
            adx = indicators["adx"]
            if isinstance(adx, dict):
                formatted["momentum_indicators"]["adx"] = adx.get("adx")
                # ADX信号判断（>25表示强趋势）
                adx_val = adx.get("adx", 0)
                if adx_val > 25:
                    formatted["momentum_indicators"][
                        "adx_signal"] = "strong_trend"
                elif adx_val > 20:
                    formatted["momentum_indicators"][
                        "adx_signal"] = "moderate_trend"
                else:
                    formatted["momentum_indicators"][
                        "adx_signal"] = "weak_trend"

        # 4. 波动率指标 (Bollinger Bands, ATR)
        if "boll" in indicators:
            boll = indicators["boll"]
            if isinstance(boll, dict):
                formatted["volatility_indicators"]["bb_upper"] = boll.get(
                    "upper")
                formatted["volatility_indicators"]["bb_middle"] = boll.get(
                    "middle")
                formatted["volatility_indicators"]["bb_lower"] = boll.get(
                    "lower")
                formatted["volatility_indicators"]["bb_width"] = boll.get(
                    "width")
                # 布林带信号判断
                if "close" in indicators and boll.get("upper") and boll.get(
                        "lower"):
                    close_price = float(indicators["close"])
                    if close_price > boll.get("upper"):
                        formatted["volatility_indicators"][
                            "bb_signal"] = "above_upper"
                    elif close_price < boll.get("lower"):
                        formatted["volatility_indicators"][
                            "bb_signal"] = "below_lower"
                    else:
                        formatted["volatility_indicators"][
                            "bb_signal"] = "within_bands"

        if "atr" in indicators:
            atr = indicators["atr"]
            if isinstance(atr, dict):
                formatted["volatility_indicators"]["atr"] = atr.get("atr")
                formatted["volatility_indicators"]["atr_pct"] = atr.get(
                    "atr_pct")

        # 5. 成交量指标
        if "volume" in indicators:
            formatted["volume_indicators"]["volume"] = indicators["volume"]
        if "volume_ma" in indicators:
            formatted["volume_indicators"]["volume_ma"] = indicators[
                "volume_ma"]

        # 6. 支撑阻力位
        if "sr" in indicators:
            sr = indicators["sr"]
            if isinstance(sr, dict):
                formatted["support_resistance"]["R1"] = sr.get("R1")
                formatted["support_resistance"]["R2"] = sr.get("R2")
                formatted["support_resistance"]["R3"] = sr.get("R3")
                formatted["support_resistance"]["S1"] = sr.get("S1")
                formatted["support_resistance"]["S2"] = sr.get("S2")
                formatted["support_resistance"]["S3"] = sr.get("S3")

        # 7. 综合信号摘要
        signals = []

        # 趋势信号
        if formatted["trend_indicators"].get("macd_signal_direction"):
            signals.append(
                f"MACD: {formatted['trend_indicators']['macd_signal_direction']}"
            )

        # 动量信号
        if formatted["momentum_indicators"].get("rsi_signal"):
            signals.append(
                f"RSI: {formatted['momentum_indicators']['rsi_signal']}")
        if formatted["momentum_indicators"].get("kdj_signal"):
            signals.append(
                f"KDJ: {formatted['momentum_indicators']['kdj_signal']}")
        if formatted["momentum_indicators"].get("adx_signal"):
            signals.append(
                f"ADX: {formatted['momentum_indicators']['adx_signal']}")

        # 波动率信号
        if formatted["volatility_indicators"].get("bb_signal"):
            signals.append(
                f"BB: {formatted['volatility_indicators']['bb_signal']}")

        formatted["signal_summary"]["signals"] = signals
        formatted["signal_summary"]["signal_count"] = len(signals)

        # 判断整体趋势
        bullish_count = sum(1 for s in signals
                            if "bullish" in s.lower() or "above" in s.lower())
        bearish_count = sum(1 for s in signals
                            if "bearish" in s.lower() or "below" in s.lower())

        if bullish_count > bearish_count:
            formatted["signal_summary"]["overall_trend"] = "bullish"
        elif bearish_count > bullish_count:
            formatted["signal_summary"]["overall_trend"] = "bearish"
        else:
            formatted["signal_summary"]["overall_trend"] = "neutral"

        return formatted

    def _clean_market_data(self, raw_market_data: Dict[str, Any],
                           symbol: str) -> Dict[str, Any]:
        """
        清洗市场数据，提取最能影响分析的指标值
        
        Args:
            raw_market_data: 原始市场数据
            symbol: 交易对
        
        Returns:
            清洗后的市场数据字典
        """
        cleaned = {
            "current_price": raw_market_data.get("price"),
            "price_change_24h": None,
            "long_short_ratio_summary": {},
            "liquidation_summary": {},
            "support_resistance_summary": {},
            "funding_rate_info": {},
            "market_sentiment": {}
        }

        # 1. 价格信息（精简版，只保留关键数据）
        if raw_market_data.get("ticker_24h"):
            ticker = raw_market_data["ticker_24h"]
            if isinstance(ticker, dict):
                # 只保留价格变化百分比，其他数据对决策影响较小
                cleaned["price_change_24h"] = {
                    "change_pct": ticker.get("priceChangePercent")  # 只保留涨跌幅百分比
                }

        # 2. 多空比数据清洗
        # participant_structure 的结构是: {dtype: {period: {current: {...}, stats: {...}, ...}}}
        participant_structure = raw_market_data.get("long_short_ratio", {})
        if participant_structure and isinstance(participant_structure, dict):
            # 尝试从 globalLongShortAccountRatio 的 5m 周期获取数据（如果没有5m，尝试其他周期）
            account_ratio_data = participant_structure.get(
                "globalLongShortAccountRatio", {})

            # 优先使用5m，如果没有则使用第一个可用的周期
            period_data = None
            for period in ["5m", "15m", "1h", "30m", "1m"]:
                if period in account_ratio_data:
                    period_data = account_ratio_data[period]
                    break

            if period_data:
                current = period_data.get("current", {})
                long_accounts_pct = current.get("long_pct")
                short_accounts_pct = current.get("short_pct")
                ls_ratio = current.get("ls_ratio")

                # 计算比率（需要处理None值）
                ratio = ls_ratio
                if ratio is None and long_accounts_pct is not None and short_accounts_pct is not None:
                    if short_accounts_pct > 0:
                        ratio = long_accounts_pct / short_accounts_pct

                cleaned["long_short_ratio_summary"] = {
                    "long_accounts_pct":
                    long_accounts_pct *
                    100 if long_accounts_pct is not None else None,  # 转换为百分比
                    "short_accounts_pct":
                    short_accounts_pct *
                    100 if short_accounts_pct is not None else None,  # 转换为百分比
                    "ratio":
                    ratio,
                    "sentiment":
                    "neutral"
                }

                # 判断多空倾向（需要处理None值）
                long_pct = long_accounts_pct * 100 if long_accounts_pct is not None else 50
                if long_pct > 55:
                    cleaned["long_short_ratio_summary"][
                        "sentiment"] = "bullish"
                elif long_pct < 45:
                    cleaned["long_short_ratio_summary"][
                        "sentiment"] = "bearish"
                else:
                    cleaned["long_short_ratio_summary"][
                        "sentiment"] = "neutral"
            else:
                # 如果没有找到数据，尝试从旧的格式获取（兼容性）
                if "longAccount" in participant_structure:
                    lsr = participant_structure
                    long_accounts_pct = lsr.get("longAccount",
                                                {}).get("percentage")
                    short_accounts_pct = lsr.get("shortAccount",
                                                 {}).get("percentage")
                    long_position_pct = lsr.get("longPosition",
                                                {}).get("percentage")
                    short_position_pct = lsr.get("shortPosition",
                                                 {}).get("percentage")

                    ratio = None
                    if long_accounts_pct is not None and short_accounts_pct is not None:
                        if short_accounts_pct > 0:
                            ratio = long_accounts_pct / short_accounts_pct

                    cleaned["long_short_ratio_summary"] = {
                        "long_accounts_pct": long_accounts_pct,
                        "short_accounts_pct": short_accounts_pct,
                        "long_position_pct": long_position_pct,
                        "short_position_pct": short_position_pct,
                        "ratio": ratio,
                        "sentiment": "neutral"
                    }

                    long_pct = long_accounts_pct if long_accounts_pct is not None else 50
                    if long_pct > 55:
                        cleaned["long_short_ratio_summary"][
                            "sentiment"] = "bullish"
                    elif long_pct < 45:
                        cleaned["long_short_ratio_summary"][
                            "sentiment"] = "bearish"
                    else:
                        cleaned["long_short_ratio_summary"][
                            "sentiment"] = "neutral"

        # 3. 爆仓数据清洗
        if raw_market_data.get("liquidation"):
            liq = raw_market_data["liquidation"]
            if isinstance(liq, dict):
                # 安全获取数值，处理None值
                buy_count = liq.get("buy_count") or 0
                sell_count = liq.get("sell_count") or 0
                buy_qty = liq.get("buy_qty") or 0.0
                sell_qty = liq.get("sell_qty") or 0.0

                # 确保数值类型正确
                try:
                    buy_count = int(buy_count) if buy_count is not None else 0
                    sell_count = int(
                        sell_count) if sell_count is not None else 0
                    buy_qty = float(buy_qty) if buy_qty is not None else 0.0
                    sell_qty = float(sell_qty) if sell_qty is not None else 0.0
                except (ValueError, TypeError):
                    buy_count = 0
                    sell_count = 0
                    buy_qty = 0.0
                    sell_qty = 0.0

                cleaned["liquidation_summary"] = {
                    "buy_liquidations": buy_count,
                    "sell_liquidations": sell_count,
                    "buy_liquidation_qty": buy_qty,
                    "sell_liquidation_qty": sell_qty,
                    "total_liquidations": buy_count + sell_count,
                    "net_liquidation_qty": buy_qty - sell_qty
                }

                # 判断爆仓倾向（需要处理除零情况）
                if sell_count > 0 and buy_count > sell_count * 1.5:
                    cleaned["liquidation_summary"][
                        "sentiment"] = "bearish"  # 多头爆仓多，看跌
                elif buy_count > 0 and sell_count > buy_count * 1.5:
                    cleaned["liquidation_summary"][
                        "sentiment"] = "bullish"  # 空头爆仓多，看涨
                else:
                    cleaned["liquidation_summary"]["sentiment"] = "neutral"

        # 4. 支撑阻力位清洗
        if raw_market_data.get("support_resistance"):
            sr = raw_market_data["support_resistance"]
            if isinstance(sr, dict):
                current_price = cleaned["current_price"]
                if current_price is not None:
                    try:
                        current_price = float(current_price)
                    except (ValueError, TypeError):
                        current_price = None

                    if current_price is not None:
                        # 精简版：只保留最近的支撑阻力位和R1/S1
                        cleaned["support_resistance_summary"] = {
                            "resistance_levels": {
                                "R1": sr.get("R1"),
                                "R2": sr.get("R2")  # 只保留R1和R2
                            },
                            "support_levels": {
                                "S1": sr.get("S1"),
                                "S2": sr.get("S2")  # 只保留S1和S2
                            },
                            "nearest_resistance": None,
                            "nearest_support": None
                        }

                        # 找到最近的支撑和阻力位（需要处理None值）
                        resistances = []
                        for r in [sr.get("R1"), sr.get("R2"), sr.get("R3")]:
                            if r is not None:
                                try:
                                    resistances.append(float(r))
                                except (ValueError, TypeError):
                                    pass

                        supports = []
                        for s in [sr.get("S1"), sr.get("S2"), sr.get("S3")]:
                            if s is not None:
                                try:
                                    supports.append(float(s))
                                except (ValueError, TypeError):
                                    pass

                        above_price = [
                            r for r in resistances if r > current_price
                        ]
                        below_price = [
                            s for s in supports if s < current_price
                        ]

                        if above_price:
                            cleaned["support_resistance_summary"][
                                "nearest_resistance"] = min(above_price)
                        if below_price:
                            cleaned["support_resistance_summary"][
                                "nearest_support"] = max(below_price)

        # 5. 资金费率信息（精简版，只保留费率值）
        if raw_market_data.get("funding_rate"):
            fr = raw_market_data["funding_rate"]
            if isinstance(fr, dict):
                cleaned["funding_rate_info"] = {
                    "funding_rate": fr.get("fundingRate")  # 只保留资金费率值
                }

        # 6. 市场情绪综合判断
        sentiment_signals = []

        if cleaned["long_short_ratio_summary"].get("sentiment"):
            sentiment_signals.append(
                f"多空比: {cleaned['long_short_ratio_summary']['sentiment']}")

        if cleaned["liquidation_summary"].get("sentiment"):
            sentiment_signals.append(
                f"爆仓: {cleaned['liquidation_summary']['sentiment']}")

        bullish_count = sum(1 for s in sentiment_signals
                            if "bullish" in s.lower())
        bearish_count = sum(1 for s in sentiment_signals
                            if "bearish" in s.lower())

        if bullish_count > bearish_count:
            cleaned["market_sentiment"]["overall"] = "bullish"
        elif bearish_count > bullish_count:
            cleaned["market_sentiment"]["overall"] = "bearish"
        else:
            cleaned["market_sentiment"]["overall"] = "neutral"

        cleaned["market_sentiment"]["signals"] = sentiment_signals

        return cleaned

    async def close(self):
        """关闭连接"""
        if self.redis:
            await self.redis.aclose()
            self.redis = None
