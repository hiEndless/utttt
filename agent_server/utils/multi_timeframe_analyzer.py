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
    
    def __init__(self, redis_host: str, redis_port: int, redis_password: str, redis_db: int):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.redis_db = redis_db
        self.redis: Optional[aioredis.Redis] = None
    
    async def connect_redis(self):
        """连接 Redis"""
        try:
            self.redis = aioredis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                db=self.redis_db,
                decode_responses=True,
                socket_connect_timeout=5
            )
            await self.redis.ping()
            return True
        except Exception as e:
            print(f"❌ Redis 连接失败: {e}")
            return False
    
    async def get_events_by_timeframe(
        self, 
        symbol: str, 
        base_timestamp_ms: int,
        timeframes: List[str] = None,
        max_age_minutes: int = 30
    ) -> Dict[str, Optional[Dict]]:
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
        
        if not self.redis:
            await self.connect_redis()
        
        max_age_ms = max_age_minutes * 60 * 1000
        min_timestamp_ms = base_timestamp_ms - max_age_ms
        
        events_by_timeframe = {}
        
        # 从各个事件流中查找对应时间维度的事件
        streams = ["final_events", "l1_events", "l0_events", "raw_event_stream"]
        
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
                    messages = await self.redis.xrevrange(
                        stream_name,
                        max="+",
                        min="-",
                        count=1000
                    )
                    
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
                                    event_data["payload"] = json.loads(event_data["payload"])
                                except:
                                    pass
                            
                            events_by_timeframe[timeframe] = event_data
                            print(f"✅ 找到 {timeframe} 事件: {event_data.get('event_id')}")
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
        
        return EventSignal(type=signal_type, payload=full_payload, strength=strength)
    
    async def analyze_multi_timeframe(
        self,
        symbol: str,
        base_event: Dict,
        timeframes: List[str] = None
    ) -> Dict[str, Any]:
        """
        分析多个时间维度的事件
        
        Args:
            symbol: 交易对
            base_event: 基础事件（触发分析的事件）
            timeframes: 时间维度列表
        
        Returns:
            包含所有时间维度分析结果的字典
        """
        if timeframes is None:
            timeframes = ["1m", "5m", "15m"]
        
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
            max_age_minutes=30
        )
        
        # 统计找到的事件
        found_count = sum(1 for v in events_by_timeframe.values() if v is not None)
        print(f"📊 找到 {found_count}/{len(timeframes)} 个时间维度的事件")
        
        # 分析每个时间维度的事件
        analysis_results = {}
        
        for timeframe, event_data in events_by_timeframe.items():
            if event_data is None:
                print(f"⚠️  {timeframe} 时间维度未找到事件")
                continue
            
            print(f"\n📈 分析 {timeframe} 时间维度...")
            
            try:
                # 转换为 EventSignal
                event_signal = self.map_event_to_signal(event_data)
                
                # 调用 Agent 系统分析
                result = await handle_event(event_signal)
                
                # 添加时间维度信息
                result["timeframe"] = timeframe
                result["event_data"] = event_data
                
                analysis_results[timeframe] = result
                
                print(f"✅ {timeframe} 分析完成")
                
            except Exception as e:
                print(f"❌ {timeframe} 分析失败: {e}")
                import traceback
                traceback.print_exc()
                analysis_results[timeframe] = {
                    "timeframe": timeframe,
                    "error": str(e),
                    "event_data": event_data
                }
        
        # 整合所有时间维度的分析结果
        integrated_result = {
            "symbol": symbol,
            "base_event": base_event,
            "timeframes": timeframes,
            "analysis_by_timeframe": analysis_results,
            "found_timeframes": [tf for tf, data in events_by_timeframe.items() if data is not None],
            "timestamp": base_timestamp_ms
        }
        
        # 调用 Agent 系统进行最终决策（传递多时间维度数据）
        # 注意：handle_event 已在文件顶部导入，这里直接使用
        final_result = await handle_event(integrated_result)
        
        # 合并结果
        final_result.update(integrated_result)
        
        return final_result
    
    async def close(self):
        """关闭连接"""
        if self.redis:
            await self.redis.aclose()
            self.redis = None

