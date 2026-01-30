"""
仓位构建器（借鉴NOFX PositionBuilder）
统一处理开仓/平仓逻辑，支持仓位合并和部分平仓
"""

import time
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PositionBuilder:
    """
    仓位构建器（借鉴NOFX PositionBuilder）
    
    功能：
    - 统一处理开仓/平仓逻辑
    - 支持仓位合并（加权平均入场价）
    - 支持部分平仓
    - 自动计算已实现盈亏
    """
    
    def __init__(self, redis_client):
        """
        初始化PositionBuilder
        
        Args:
            redis_client: Redis客户端实例
        """
        self.redis = redis_client
        self.exchange = "binance"  # 默认交易所
    
    async def process_trade(self, trade_data: Dict[str, Any]) -> bool:
        """
        处理交易，自动更新仓位
        
        Args:
            trade_data: 交易数据字典，包含：
                - order_type: 'open' 或 'close'
                - symbol: 交易对符号
                - position_side: 'LONG' 或 'SHORT'
                - quantity: 数量
                - openAvgPx: 开仓均价（开仓时）
                - closeAvgPx: 平仓均价（平仓时）
        
        Returns:
            bool: 是否成功处理
        """
        try:
            action = trade_data.get('order_type', '').lower()
            symbol = trade_data.get('symbol', '')
            
            if not symbol:
                logger.error("缺少交易对符号")
                return False
            
            if action == 'open':
                return await self._handle_open(trade_data)
            elif action == 'close':
                return await self._handle_close(trade_data)
            else:
                logger.warning(f"未知的交易类型: {action}")
                return False
        except Exception as e:
            logger.error(f"处理交易失败: {e}", exc_info=True)
            return False
    
    async def _handle_open(self, trade_data: Dict[str, Any]) -> bool:
        """
        开仓：创建新仓位或合并到现有仓位（加权平均入场价）
        
        Args:
            trade_data: 交易数据
        
        Returns:
            bool: 是否成功
        """
        try:
            symbol = trade_data['symbol']
            side = trade_data.get('position_side', 'LONG')
            new_qty = float(trade_data.get('quantity', 0))
            new_price = float(trade_data.get('openAvgPx', 0))
            
            if new_qty <= 0 or new_price <= 0:
                logger.error(f"无效的开仓数据: qty={new_qty}, price={new_price}")
                return False
            
            position_key = f"position:{self.exchange}:{symbol}:{side}"
            
            # 检查是否已有仓位
            existing = await self.redis.hgetall(position_key)
            
            if existing:
                # 合并仓位，计算加权平均入场价（借鉴NOFX）
                old_qty = float(existing.get('quantity', 0))
                old_price = float(existing.get('entry_price', 0))
                
                if old_qty <= 0 or old_price <= 0:
                    logger.warning(f"现有仓位数据无效，创建新仓位: {symbol} {side}")
                    existing = None
            
            if existing:
                # 合并仓位
                total_qty = old_qty + new_qty
                # 加权平均入场价
                avg_price = (old_price * old_qty + new_price * new_qty) / total_qty
                
                logger.info(
                    f"合并仓位: {symbol} {side} | "
                    f"旧: {old_qty:.6f} @ {old_price:.2f} + "
                    f"新: {new_qty:.6f} @ {new_price:.2f} = "
                    f"{total_qty:.6f} @ {avg_price:.2f}"
                )
                
                await self.redis.hset(position_key, {
                    'quantity': total_qty,
                    'entry_price': avg_price,
                    'updated_at': int(time.time() * 1000)
                })
            else:
                # 创建新仓位
                logger.info(f"创建新仓位: {symbol} {side} | {new_qty:.6f} @ {new_price:.2f}")
                
                await self.redis.hset(position_key, {
                    'symbol': symbol,
                    'side': side,
                    'quantity': new_qty,
                    'entry_price': new_price,
                    'created_at': int(time.time() * 1000),
                    'updated_at': int(time.time() * 1000)
                })
                
                # 添加到开仓集合
                await self.redis.sadd(f"trading:open_positions:{self.exchange}", symbol)
            
            return True
        except Exception as e:
            logger.error(f"处理开仓失败: {e}", exc_info=True)
            return False
    
    async def _handle_close(self, trade_data: Dict[str, Any]) -> bool:
        """
        平仓：部分平仓或完全平仓（借鉴NOFX）
        
        Args:
            trade_data: 交易数据
        
        Returns:
            bool: 是否成功
        """
        try:
            symbol = trade_data['symbol']
            side = trade_data.get('position_side', 'LONG')
            close_qty = float(trade_data.get('quantity', 0))
            close_price = float(trade_data.get('closeAvgPx', 0))
            
            if close_qty <= 0:
                logger.error(f"无效的平仓数量: {close_qty}")
                return False
            
            position_key = f"position:{self.exchange}:{symbol}:{side}"
            position = await self.redis.hgetall(position_key)
            
            if not position:
                logger.warning(f"未找到仓位: {symbol} {side}")
                return False
            
            position_qty = float(position.get('quantity', 0))
            entry_price = float(position.get('entry_price', 0))
            
            if position_qty <= 0:
                logger.warning(f"仓位数量为0: {symbol} {side}")
                return False
            
            # 计算已实现盈亏（借鉴NOFX）
            if entry_price > 0 and close_price > 0:
                if side == 'LONG':
                    realized_pnl = (close_price - entry_price) * close_qty
                else:  # SHORT
                    realized_pnl = (entry_price - close_price) * close_qty
                # 保留2位小数
                realized_pnl = round(realized_pnl, 2)
            else:
                realized_pnl = 0.0
            
            # 数量容差（借鉴NOFX）
            QUANTITY_TOLERANCE = 0.0001
            
            if close_qty < position_qty - QUANTITY_TOLERANCE:
                # 部分平仓
                new_qty = position_qty - close_qty
                logger.info(
                    f"部分平仓: {symbol} {side} | "
                    f"{position_qty:.6f} → {new_qty:.6f} "
                    f"(平仓 {close_qty:.6f} @ {close_price:.2f}, PnL: {realized_pnl:.2f})"
                )
                
                await self.redis.hset(position_key, {
                    'quantity': new_qty,
                    'updated_at': int(time.time() * 1000)
                })
            else:
                # 完全平仓（或接近完全平仓）
                if close_qty > position_qty:
                    logger.warning(
                        f"超量平仓: {symbol} {side} | "
                        f"尝试平仓 {close_qty:.6f} 但只有 {position_qty:.6f}，平仓全部"
                    )
                    close_qty = position_qty
                
                logger.info(
                    f"完全平仓: {symbol} {side} | "
                    f"{close_qty:.6f} @ {close_price:.2f} "
                    f"(入场: {entry_price:.2f}, PnL: {realized_pnl:.2f})"
                )
                
                # 删除仓位记录
                await self.redis.delete(position_key)
                
                # 从开仓集合中移除
                await self.redis.srem(f"trading:open_positions:{self.exchange}", symbol)
            
            return True
        except Exception as e:
            logger.error(f"处理平仓失败: {e}", exc_info=True)
            return False
    
    async def get_position(self, symbol: str, side: str = 'LONG') -> Optional[Dict[str, Any]]:
        """
        获取仓位信息
        
        Args:
            symbol: 交易对符号
            side: 仓位方向（LONG/SHORT）
        
        Returns:
            仓位信息字典，如果不存在返回None
        """
        try:
            position_key = f"position:{self.exchange}:{symbol}:{side}"
            position = await self.redis.hgetall(position_key)
            
            if not position:
                return None
            
            return {
                'symbol': position.get('symbol', symbol),
                'side': position.get('side', side),
                'quantity': float(position.get('quantity', 0)),
                'entry_price': float(position.get('entry_price', 0)),
                'created_at': int(position.get('created_at', 0)),
                'updated_at': int(position.get('updated_at', 0))
            }
        except Exception as e:
            logger.error(f"获取仓位失败: {e}", exc_info=True)
            return None
    
    async def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有仓位
        
        Returns:
            仓位字典，key为 "{symbol}:{side}"
        """
        try:
            # 获取所有开仓的交易对
            symbols = await self.redis.smembers(f"trading:open_positions:{self.exchange}")
            
            positions = {}
            for symbol in symbols:
                # 检查LONG和SHORT两个方向
                for side in ['LONG', 'SHORT']:
                    position = await self.get_position(symbol, side)
                    if position and position['quantity'] > 0:
                        key = f"{symbol}:{side}"
                        positions[key] = position
            
            return positions
        except Exception as e:
            logger.error(f"获取所有仓位失败: {e}", exc_info=True)
            return {}
