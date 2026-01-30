"""
实时仓位监控服务（借鉴NOFX实时仓位监控）
定期检查已开仓位的风险，执行止损、止盈等风控操作
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from agent_server.utils.redis_client import RedisClient
from agent_server.utils.position_builder import PositionBuilder
from agent_server.utils.risk_control import RiskController
from agent_server.tools.price_fetcher import get_mark_price_from_redis

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PositionMonitor:
    """
    实时仓位监控服务（借鉴NOFX）
    
    功能：
    - 定期检查已开仓位的风险
    - 执行止损、止盈等风控操作
    - 监控仓位盈亏情况
    """
    
    def __init__(
        self,
        check_interval: int = 60,  # 检查间隔（秒），默认60秒
        exchange: str = "binance"
    ):
        """
        初始化仓位监控服务
        
        Args:
            check_interval: 检查间隔（秒）
            exchange: 交易所名称
        """
        self.check_interval = check_interval
        self.exchange = exchange
        self.position_builder = PositionBuilder(RedisClient())
        self.risk_controller = RiskController()
        self._running = False
        self._task = None
    
    async def check_all_positions(self) -> List[Dict[str, Any]]:
        """
        检查所有已开仓位的风险
        
        Returns:
            需要风控操作的仓位列表
        """
        try:
            # 获取所有仓位
            all_positions = await self.position_builder.get_all_positions()
            
            if not all_positions:
                logger.debug("没有已开仓位")
                return []
            
            risk_positions = []
            
            for position_key, position in all_positions.items():
                symbol = position.get('symbol', '')
                side = position.get('side', 'LONG')
                
                if not symbol:
                    continue
                
                # 获取当前价格
                current_price = await get_mark_price_from_redis(self.exchange, symbol)
                
                if not current_price or current_price <= 0:
                    logger.warning(f"无法获取价格: {symbol}")
                    continue
                
                # 检查仓位风险
                needs_action, risk_desc, suggested_action = await self.risk_controller.check_position_risk(
                    position, current_price
                )
                
                if needs_action:
                    risk_positions.append({
                        'position_key': position_key,
                        'symbol': symbol,
                        'side': side,
                        'position': position,
                        'current_price': current_price,
                        'risk_desc': risk_desc,
                        'suggested_action': suggested_action
                    })
                    
                    logger.warning(
                        f"仓位风险警告: {symbol} {side} | {risk_desc} | 建议操作: {suggested_action}"
                    )
                else:
                    logger.debug(f"仓位正常: {symbol} {side} | {risk_desc}")
            
            return risk_positions
        except Exception as e:
            logger.error(f"检查仓位风险失败: {e}", exc_info=True)
            return []
    
    async def handle_risk_positions(self, risk_positions: List[Dict[str, Any]]):
        """
        处理有风险的仓位（可以扩展为自动执行止损/止盈）
        
        Args:
            risk_positions: 有风险的仓位列表
        """
        for risk_pos in risk_positions:
            symbol = risk_pos['symbol']
            side = risk_pos['side']
            suggested_action = risk_pos['suggested_action']
            risk_desc = risk_pos['risk_desc']
            
            logger.info(
                f"处理仓位风险: {symbol} {side} | {risk_desc} | 建议: {suggested_action}"
            )
            
            # TODO: 可以在这里实现自动止损/止盈逻辑
            # 例如：如果suggested_action是"CLOSE"，可以推送平仓订单到交易队列
            # 目前只记录日志，不自动执行，需要人工确认
    
    async def monitor_loop(self):
        """监控循环"""
        logger.info(f"仓位监控服务启动，检查间隔: {self.check_interval}秒")
        
        while self._running:
            try:
                # 检查所有仓位
                risk_positions = await self.check_all_positions()
                
                if risk_positions:
                    logger.warning(f"发现 {len(risk_positions)} 个有风险的仓位")
                    await self.handle_risk_positions(risk_positions)
                else:
                    logger.debug("所有仓位正常")
                
                # 等待下次检查
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"仓位监控循环错误: {e}", exc_info=True)
                await asyncio.sleep(60)  # 出错后等待1分钟再重试
    
    async def start(self):
        """启动监控服务"""
        if self._running:
            logger.warning("仓位监控服务已在运行")
            return
        
        self._running = True
        self._task = asyncio.create_task(self.monitor_loop())
        logger.info("仓位监控服务已启动")
    
    async def stop(self):
        """停止监控服务"""
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("仓位监控服务已停止")
    
    def is_running(self) -> bool:
        """检查服务是否在运行"""
        return self._running


# 全局实例（可选）
_position_monitor: Optional[PositionMonitor] = None


def get_position_monitor(check_interval: int = 60) -> PositionMonitor:
    """
    获取全局仓位监控实例
    
    Args:
        check_interval: 检查间隔（秒）
    
    Returns:
        PositionMonitor实例
    """
    global _position_monitor
    if _position_monitor is None:
        _position_monitor = PositionMonitor(check_interval=check_interval)
    return _position_monitor


if __name__ == "__main__":
    # 测试代码
    async def test():
        monitor = PositionMonitor(check_interval=30)
        await monitor.start()
        
        try:
            # 运行5分钟
            await asyncio.sleep(300)
        finally:
            await monitor.stop()
    
    asyncio.run(test())
