import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor
from agent_server.utils.db_utils import PostgresDB
from agent_server.tools.get_position import get_position
from agent_server.tools.price_fetcher import get_mark_price_sync

logger = logging.getLogger(__name__)


class TradeEventRecorder:
    """
    异步交易事件记录器
    负责将 final_events 流中的事件信息存入数据库 (trade_events 表)
    """
    
    def __init__(self, max_workers: int = 3):
        """
        初始化记录器
        :param max_workers: 线程池大小，用于异步执行同步数据库操作
        """
        self.db = PostgresDB()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
    def _safe_parse_json(self, data: str) -> Dict[str, Any]:
        """安全解析 JSON 字符串"""
        if not data:
            return {}
        try:
            if isinstance(data, str):
                return json.loads(data)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"JSON 解析失败: {e}, 原始数据: {data[:100]}")
            return {}
    
    def _get_trade_ids_from_redis(self, exchange: str, symbol: str) -> List[str]:
        """
        从 Redis 获取当前活跃的 trade_id 列表
        支持多空双开：同一个交易对可能有 LONG 和 SHORT 两个持仓
        
        :return: trade_id 列表（可能包含多个）
        """
        try:
            # 使用 get_position 从 Redis 获取持仓信息
            positions = get_position(exchange, symbol)
            
            trade_ids = []
            for pos in positions:
                trade_id = pos.get("trade_id")
                if trade_id:
                    trade_ids.append(trade_id)
                    logger.debug(
                        f"从 Redis 获取 trade_id: {trade_id} "
                        f"({symbol}, {pos.get('position_side')}, size={pos.get('size')})"
                    )
            
            return trade_ids
            
        except Exception as e:
            logger.error(f"从 Redis 获取持仓失败: {e}, exchange={exchange}, symbol={symbol}")
            return []
    
    def _extract_event_type(self, event_info: Dict[str, Any]) -> str:
        """
        提取事件类型
        优先使用 event_type 字段，如果没有则根据 route 映射
        """
        # 1. 优先使用原始 event_type (如 trade.open, trade.close)
        raw_type = event_info.get("event_type") or ""
        if raw_type:
            return raw_type
        return event_info.get("route") or "unknown"
    
    def _extract_direction(self, event_info: Dict[str, Any]) -> str:
        """
        提取方向信息
        1. 交易类事件：从 trade_details.position_side 提取 (LONG -> bullish, SHORT -> bearish)
        2. 分析类事件：从 direction 字段获取 (bullish/bearish/neutral)
        """
        # 1. 交易类事件处理
        route = event_info.get("route")
        event_type = event_info.get("event_type", "")
        
        if route == "trade" or event_type.startswith("trade."):
            trade_details = event_info.get("trade_details") or {}
            position_side = trade_details.get("position_side")
            if position_side:
                # 统一映射为 bullish/bearish 以符合数据模型定义
                side = position_side.upper()
                if side == "LONG":
                    return "bullish"
                elif side == "SHORT":
                    return "bearish"
                return "neutral"
        
        # 2. 现有逻辑（分析类事件）
        direction = event_info.get("direction", "")
        if isinstance(direction, str):
            direction = direction.lower()
            if direction in ("bullish", "bearish", "neutral"):
                return direction
        
        return "neutral"
    
    def _extract_market_context(self, event_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取市场背景快照（占位）
        注意：真实的 market_context 应该在 Agent 分析完成后，通过 update_event_context() 方法补充
        这里只保存事件本身携带的基础信息
        """
        return {
            "event_source": event_info.get("route"),
            "captured_at": event_info.get("timestamp"),
            "note": "市场背景快照待 Agent 分析后补充"
        }
    
    def _extract_event_data(self, event_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取事件原始数据
        - 对于 indicators 事件，存储 analysis_context
        - 对于 trade 事件，存储 trade_details
        """
        route = event_info.get("route")
        
        # 根据路由类型选择主要数据源
        if route == "trade":
            primary_data = event_info.get("trade_details")
        else:
            # 默认为 analysis_context (适用于 indicators 等)
            primary_data = event_info.get("analysis_context")
            
        if primary_data and isinstance(primary_data, dict):
            data = primary_data.copy()
            # 补充基础元数据
            data.update({
                "event_id": event_info.get("event_id"),
                "route": route,
            })
            return data
        return {}

    
    def _extract_indicators_snapshot(self, event_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        提取关键技术指标快照
        indicators 路由才有，从 Redis 或其他来源获取
        这里先返回基础信息，后续可扩展
        """
        if event_info.get("route") != "indicators":
            return None
        
        # TODO: 可以从 Redis 读取完整的指标快照
        # 这里先返回事件携带的基础信息
        return {
            "l1_total_score": event_info.get("l1_total_score"),
            "tf_hint": event_info.get("tf_hint"),
            "confidence": event_info.get("confidence"),
        }
    
    def _get_or_create_trade_id(self, exchange: str, symbol: str, position_side: Optional[str] = None) -> List[str]:
        """
        获取当前活跃的 trade_id 列表
        支持多空双开：如果同一个交易对有 LONG 和 SHORT 两个持仓，返回两个 trade_id
        
        查询优先级：
        1. 先从 Redis 获取（实时持仓信息）
        2. Redis 未找到，再查询数据库（未平仓交易）
        
        :param exchange: 交易所
        :param symbol: 交易对
        :param position_side: 持仓方向（可选），如果指定则只返回该方向的 trade_id
        :return: trade_id 列表（多空双开时可能有多个）
        """
        trade_ids = []
        
        # 1. 优先从 Redis 获取（最新的持仓信息）
        try:
            redis_trade_ids = self._get_trade_ids_from_redis(exchange, symbol)
            
            if redis_trade_ids:
                # 如果指定了 position_side，需要过滤
                if position_side:
                    with PostgresDB() as db:
                        # 需要查询每个 trade_id 对应的 position_side
                        for tid in redis_trade_ids:
                            sql = "SELECT position_side FROM trades WHERE trade = %s AND close_time IS NULL"
                            result = db.fetch_one(sql, [tid])
                            if result and result.get("position_side") == position_side:
                                trade_ids.append(tid)
                else:
                    trade_ids = redis_trade_ids
                
                if trade_ids:
                    logger.info(
                        f"从 Redis 获取活跃交易: exchange={exchange}, symbol={symbol}, "
                        f"position_side={position_side}, trade_ids={trade_ids}"
                    )
                    return trade_ids
        except Exception as e:
            logger.warning(f"从 Redis 获取 trade_id 失败: {e}, 降级到数据库查询")
        
        # 2. Redis 未找到，查询数据库（未平仓的交易）
        try:
            with PostgresDB() as db:
                sql = """
                    SELECT trade, position_side FROM trades
                    WHERE exchange = %s AND symbol = %s AND close_time IS NULL
                """
                params = [exchange, symbol]
                
                if position_side:
                    sql += " AND position_side = %s"
                    params.append(position_side)
                
                sql += " ORDER BY entry_time DESC"
                
                results = db.fetch_all(sql, params)
                
                if results:
                    for row in results:
                        trade_id = row[0] if isinstance(row, tuple) else row.get("trade")
                        if trade_id:
                            trade_ids.append(trade_id)
                    
                    logger.info(
                        f"从数据库获取活跃交易: exchange={exchange}, symbol={symbol}, "
                        f"position_side={position_side}, trade_ids={trade_ids}"
                    )
                    return trade_ids
            
            logger.warning(
                f"未找到活跃交易: exchange={exchange}, symbol={symbol}, position_side={position_side}"
            )
            return []
            
        except Exception as e:
            logger.error(f"查询 trade_id 失败: {e}")
            return []
    
    def _save_event_sync(self, trade_id: str, event_info: Dict[str, Any], mark_price: Optional[float] = None):
        """
        同步保存事件到数据库 (内部方法，由线程池执行)
        """
        try:
            event_id = event_info.get("event_id", "")
            event_type = self._extract_event_type(event_info)
            exchange = event_info.get("exchange", "").lower()
            symbol = event_info.get("symbol", "")
            user_id = str(event_info.get("user_id") or "").strip() or None
            exchange_account_id = str(event_info.get("exchange_account_id") or "").strip() or None
            
            # 时间戳转换为毫秒（如果不是）
            event_at = int(event_info.get("timestamp", 0))
            if event_at < 10**12:  # 如果是秒级时间戳，转为毫秒
                event_at = event_at * 1000
            direction = self._extract_direction(event_info)
            
            # market_context = self._extract_market_context(event_info)
            market_context = None
            event_data = self._extract_event_data(event_info)
            indicators_snapshot = self._extract_indicators_snapshot(event_info)
            
            # 判断是否需要自动标记为已验证（仅针对交易事件：跳过分析的事件）
            is_verified = False
            event_summary = None
            
            if event_info.get("route") == "trade":
                # 1. 开仓/平仓事件
                is_open_event = "trade.open" in event_type.lower()
                is_close_event = "trade.close" in event_type.lower()
                
                # 2. 短线交易事件 (从 event_info 获取，或者从 meta 获取)
                is_short_term = event_info.get("is_short_term")
                if is_short_term is None:
                    meta = event_info.get("meta") or {}
                    raw_short = meta.get("is_short_term")
                    if isinstance(raw_short, str):
                        is_short_term = raw_short.lower() == "true"
                    else:
                        is_short_term = bool(raw_short)
                
                if is_open_event:
                    is_verified = True
                    event_summary = "系统策略：开仓事件不进行分析"
                elif is_close_event:
                    is_verified = True
                    event_summary = "系统策略：平仓事件不进行分析"
                elif is_short_term:
                    is_verified = True
                    event_summary = "系统策略：短线高频交易不进行分析"

            # 插入 trade_events 表
            # 注意：外键字段名是 trade_id (对应 Trade 模型的 trade 字段)
            # 多空双开场景：同一 event_id 可能对应多个 trade_id
            # 通过 (event_id, trade_id) 联合唯一来区分不同持仓的事件
            
            with PostgresDB() as db:
                check_sql = "SELECT id, is_verified FROM trade_events WHERE event_id = %s AND trade_id = %s LIMIT 1"
                existing = db.fetch_one(check_sql, [event_id, trade_id])
                
                if existing:
                    # 已存在，更新记录
                    # 如果本次判定需要验证，或者数据库中已经是验证状态，则保持为 True
                    # 避免将已验证（True）的记录覆盖为未验证（False）
                    db_is_verified = existing[1] if isinstance(existing, tuple) else existing.get("is_verified")
                    final_is_verified = is_verified or db_is_verified
                    
                    # 构建更新语句
                    update_sql = """
                        UPDATE trade_events SET
                            event_at = %s,
                            mark_price = %s,
                            market_context = %s,
                            event_data = %s,
                            indicators_snapshot = %s,
                            symbol = %s,
                            exchange = %s,
                            user_id = COALESCE(user_id, %s),
                            exchange_account_id = COALESCE(exchange_account_id, %s),
                            is_verified = %s
                    """
                    update_params = [
                        event_at,
                        mark_price,
                        json.dumps(market_context, ensure_ascii=False),
                        json.dumps(event_data, ensure_ascii=False),
                        json.dumps(indicators_snapshot, ensure_ascii=False) if indicators_snapshot else None,
                        symbol,
                        exchange,
                        user_id,
                        exchange_account_id,
                        final_is_verified
                    ]
                    
                    # 只有当本次有特定的 summary 时才更新该字段，避免覆盖人工 summary
                    if event_summary:
                        update_sql += ", event_summary = %s"
                        update_params.append(event_summary)
                        
                    update_sql += " WHERE event_id = %s AND trade_id = %s"
                    update_params.extend([event_id, trade_id])
                    
                    db.execute(update_sql, update_params)
                    logger.info(f"事件已更新: trade_id={trade_id}, event_id={event_id}, event_type={event_type}")
                else:
                    # 不存在，插入新记录
                    sql = """
                        INSERT INTO trade_events (
                            trade_id, event_id, event_type, event_at,
                            direction, mark_price,
                            market_context, event_data, indicators_snapshot,
                            is_verified, verification_at,
                            symbol, exchange,
                            user_id, exchange_account_id,
                            event_summary
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s,
                            %s
                        )
                    """
                    
                    params = [
                        trade_id,
                        event_id,  # 保持原始 event_id 格式
                        event_type,
                        event_at,
                        direction,
                        mark_price,
                        json.dumps(market_context, ensure_ascii=False),
                        json.dumps(event_data, ensure_ascii=False),
                        json.dumps(indicators_snapshot, ensure_ascii=False) if indicators_snapshot else None,
                        is_verified,  # 使用计算出的 is_verified
                        None,   # verification_at
                        symbol,
                        exchange,
                        user_id,
                        exchange_account_id,
                        event_summary
                    ]
                    
                    db.execute(sql, params)
                    logger.info(f"事件已入库: trade_id={trade_id}, event_id={event_id}, event_type={event_type}")
            
        except Exception as e:
            logger.error(f"事件入库失败: {e}, trade_id={trade_id}", exc_info=True)
            raise
    
    async def save_event(self, event_info: Dict[str, Any], mark_price: Optional[float] = None) -> bool:
        """
        异步保存事件到数据库
        支持多空双开：如果同一交易对有 LONG 和 SHORT 两个持仓，会为两个持仓分别保存事件记录
        
        :param event_info: 来自 final_listen_main.py 的 info 字典
        :param mark_price: 事件发生时的价格（可选）
        :return: 是否成功
        """
        try:
            # 1. 提取基础信息
            exchange = event_info.get("exchange", "").lower()
            symbol = event_info.get("symbol", "")
            
            if not exchange or not symbol:
                logger.warning(f"缺少必要字段: exchange={exchange}, symbol={symbol}")
                return False
            
            # 2. 确定 trade_ids
            # 如果是 trade 事件，直接从 trade_details 获取 trade_id
            trade_ids = []
            trade_details = event_info.get("trade_details") or {}
            direct_trade_id = trade_details.get("trade_id")
            
            if direct_trade_id:
                trade_ids = [direct_trade_id]
                logger.debug(f"直接使用事件携带的 trade_id: {direct_trade_id}")
            else:
                # 否则从 Redis 或数据库获取所有活跃的 trade_id
                loop = asyncio.get_event_loop()
                trade_ids = await loop.run_in_executor(
                    self.executor,
                    self._get_or_create_trade_id,
                    exchange,
                    symbol,
                    None  # position_side=None，获取所有持仓
                )
            
            if not trade_ids:
                logger.warning(f"无法关联 trade_id，跳过入库: exchange={exchange}, symbol={symbol}")
                return False
            
            # 3. 为每个 trade_id 保存事件（多空双开时会保存多条记录）
            loop = asyncio.get_event_loop()
            save_tasks = [
                loop.run_in_executor(
                    self.executor,
                    self._save_event_sync,
                    tid,
                    event_info,
                    mark_price
                )
                for tid in trade_ids
            ]
            
            # 并发保存
            results = await asyncio.gather(*save_tasks, return_exceptions=True)
            errors = [r for r in results if isinstance(r, Exception)]
            if errors:
                logger.error(
                    f"事件入库存在失败项: exchange={exchange}, symbol={symbol}, trade_ids={trade_ids}, "
                    f"errors_count={len(errors)}"
                )
                for idx, err in enumerate(errors[:5]):
                    logger.error(f"入库异常[{idx}]: {err}", exc_info=err)
                return False
            
            logger.info(
                f"事件已保存到 {len(trade_ids)} 个持仓: "
                f"exchange={exchange}, symbol={symbol}, trade_ids={trade_ids}"
            )
            return True
            
        except Exception as e:
            logger.error(f"异步保存事件失败: {e}", exc_info=True)
            return False
    
    async def batch_save_events(self, events: list[Dict[str, Any]]) -> int:
        """
        批量保存事件（并发）
        :param events: 事件列表
        :return: 成功保存的数量
        """
        tasks = [self.save_event(event) for event in events]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if r is True)
        logger.info(f"批量保存完成: 总数={len(events)}, 成功={success_count}")
        return success_count
    
    async def update_event_context(self, event_id: str, exchange: str, symbol: str, market_context: Dict[str, Any]) -> bool:
        """
        更新事件的市场背景快照（由 Agent 分析后调用）
        
        注意：如果是多空双开场景，同一个 event_id 可能对应多条 trade_events 记录（不同的 trade_id）。
        此方法会更新所有匹配 event_id 的记录。
        
        :param event_id: 事件ID
        :param exchange: 交易所
        :param symbol: 交易对
        :param market_context: 从 Redis 读取的 market_state 数据
        :return: 是否成功
        """
        try:
            def _update_sync():
                with PostgresDB() as db:
                    # 检查事件是否存在（至少存在一条）
                    check_sql = "SELECT id FROM trade_events WHERE event_id = %s LIMIT 1"
                    existing = db.fetch_one(check_sql, [event_id])
                    
                    if not existing:
                        logger.warning(f"事件不存在，无法更新: event_id={event_id}")
                        return False
                    
                    # 更新所有匹配 event_id 的记录的 market_context 字段
                    # 无论是多空双开还是单开，只要 event_id 匹配，说明它们共享同一个市场背景
                    update_sql = """
                        UPDATE trade_events 
                        SET market_context = %s
                        WHERE event_id = %s
                    """
                    db.execute(update_sql, [
                        json.dumps(market_context, ensure_ascii=False),
                        event_id
                    ])
                    
                    logger.info(f"市场背景快照已更新: event_id={event_id}, exchange={exchange}, symbol={symbol}")
                    return True
            
            # 异步执行
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self.executor, _update_sync)
            return result
            
        except Exception as e:
            logger.error(f"更新市场背景快照失败: {e}, event_id={event_id}", exc_info=True)
            return False

    async def update_market_structure(self, event_id: str, market_structure: Dict[str, Any]) -> bool:
        """
        更新事件的市场结构分析结果
        
        :param event_id: 事件ID
        :param market_structure: 市场结构分析结果
        :return: 是否成功
        """
        try:
            def _update_sync():
                with PostgresDB() as db:
                    # 检查事件是否存在
                    check_sql = "SELECT id FROM trade_events WHERE event_id = %s LIMIT 1"
                    existing = db.fetch_one(check_sql, [event_id])
                    
                    if not existing:
                        logger.warning(f"事件不存在，无法更新 market_structure: event_id={event_id}")
                        return False
                    
                    # 更新所有匹配 event_id 的记录
                    update_sql = """
                        UPDATE trade_events 
                        SET market_structure = %s
                        WHERE event_id = %s
                    """
                    db.execute(update_sql, [
                        json.dumps(market_structure, ensure_ascii=False),
                        event_id
                    ])
                    
                    logger.info(f"市场结构已更新: event_id={event_id}")
                    return True
            
            # 异步执行
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self.executor, _update_sync)
            return result
            
        except Exception as e:
            logger.error(f"更新市场结构失败: {e}, event_id={event_id}", exc_info=True)
            return False

    async def save_agent_analysis(
        self,
        event_id: str,
        agent_name: str,
        analysis_data: Dict[str, Any],
        exchange: str,
        symbol: str,
        trade_id: Optional[str] = None,
        model_version: Optional[str] = None,
        *,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        保存 Agent 分析结果 (agent_analyses 表)
        
        :param symbol:
        :param exchange:
        :param event_id: 关联的事件ID
        :param agent_name: Agent 名称 (e.g. signal_validation, position_risk)
        :param analysis_data: 分析结果字典
        :param trade_id: 可选。如果指定，只保存到该交易关联的事件记录；否则保存到该 event_id 关联的所有记录。
        :param model_version: 模型版本
        :param user_id: 可选。用于在 trade_events.user_id 缺失时的兜底写入
        :return: 是否成功
        """
        try:
            def _save_sync():
                with PostgresDB() as db:
                    # 1. 找到关联的 trade_events
                    sql = "SELECT id, user_id, exchange_account_id FROM trade_events WHERE event_id = %s"
                    params = [event_id]
                    
                    if trade_id:
                        sql += " AND trade_id = %s"
                        params.append(trade_id)
                    
                    event_rows = db.fetch_all(sql, params)
                    
                    if not event_rows:
                        logger.warning(f"无法保存分析结果: 未找到对应的事件记录, event_id={event_id}, trade_id={trade_id}")
                        return False
                    
                    event_db_items = []
                    for row in event_rows:
                        if isinstance(row, tuple):
                            event_db_items.append(
                                {
                                    "id": row[0],
                                    "user_id": row[1],
                                    "exchange_account_id": row[2],
                                }
                            )
                        else:
                            event_db_items.append(
                                {
                                    "id": row.get("id"),
                                    "user_id": row.get("user_id"),
                                    "exchange_account_id": row.get("exchange_account_id"),
                                }
                            )
                    
                    # 2. 提取通用字段
                    # agent_analyses 表已移除 verdict 字段，这里不再单独落库 verdict
                    risk_action = analysis_data.get("risk_action")
                    # 优先使用传入的 model_version 参数，如果没有则从 analysis_data 中获取
                    final_model_version = model_version or analysis_data.get("model_version")
                    meta = analysis_data.get("meta") if isinstance(analysis_data, dict) else None
                    meta_uid = None
                    if isinstance(meta, dict):
                        meta_uid = str(meta.get("user_id") or meta.get("uid") or "").strip() or None
                    fallback_user_id = str(user_id or meta_uid or "").strip() or None
                    
                    # 获取实时 mark_price
                    mark_price = get_mark_price_sync({"symbol": symbol, "exchange": exchange}, exchange)
                    if mark_price is None:
                        mark_price = analysis_data.get("mark_price")

                    reasoning = analysis_data.get("reasoning")
                    full_output = analysis_data  # 整个数据存为 full_output
                    
                    # 3. 为每个关联的事件插入分析记录
                    insert_sql = """
                        INSERT INTO agent_analyses (
                            event_id, agent_name, model_version,
                            risk_action, mark_price,
                            reasoning, full_output, created_at,
                            symbol, exchange,
                            user_id, exchange_account_id
                        ) VALUES (
                            %s, %s, %s,
                            %s, %s,
                            %s, %s, NOW(),
                            %s, %s,
                            %s, %s
                        )
                    """
                    
                    for item in event_db_items:
                        # 中文注释：优先使用事件记录上的 user_id；若缺失，则使用外部传入/analysis_data.meta 的 user_id 兜底
                        final_user_id = item.get("user_id") or fallback_user_id
                        db.execute(insert_sql, [
                            item.get("id"),
                            agent_name,
                            final_model_version,
                            risk_action,
                            mark_price,
                            json.dumps(reasoning, ensure_ascii=False) if reasoning else None,
                            json.dumps(full_output, ensure_ascii=False),
                            symbol,
                            exchange,
                            final_user_id,
                            item.get("exchange_account_id"),
                        ])
                    
                    logger.info(f"Agent分析结果已保存: {agent_name}, event_id={event_id}, 关联记录数={len(event_db_items)}")
                    return True

            # 异步执行
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self.executor, _save_sync)
            return result
            
        except Exception as e:
            logger.error(f"保存Agent分析结果失败: {e}, agent={agent_name}", exc_info=True)
            return False

    def close(self):
        """关闭资源"""
        try:
            self.db.disconnect()
            self.executor.shutdown(wait=True)
            logger.info("TradeEventRecorder 资源已释放")
        except Exception as e:
            logger.error(f"关闭资源失败: {e}")


# 全局单例（可选）
_recorder_instance = None

def get_recorder() -> TradeEventRecorder:
    """获取全局记录器单例"""
    global _recorder_instance
    if _recorder_instance is None:
        _recorder_instance = TradeEventRecorder()
    return _recorder_instance
