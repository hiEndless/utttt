"""
仓位风控控制器（借鉴NOFX双层风控系统）
代码级风控：硬性限制，不依赖AI
"""

import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class RiskController:
    """
    仓位风控控制器（借鉴NOFX双层风控系统）
    
    代码级风控（CODE ENFORCED）：
    - 最大仓位数量限制
    - 单仓位价值比例限制（BTC/ETH vs Altcoin不同）
    - 最小仓位大小限制
    - 最大保证金使用率限制
    - 最小风险回报比限制
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化风控控制器
        
        Args:
            config: 配置字典，包含：
                - max_positions: 最大仓位数量（默认3）
                - btc_eth_max_position_ratio: BTC/ETH最大仓位比例（默认5.0）
                - altcoin_max_position_ratio: Altcoin最大仓位比例（默认1.0）
                - min_position_size: 最小仓位大小（USD，默认12.0）
                - max_margin_usage: 最大保证金使用率（默认0.9）
                - min_risk_reward_ratio: 最小风险回报比（默认3.0）
        """
        config = config or {}
        self.max_positions = config.get('max_positions', 3)
        self.btc_eth_max_ratio = config.get('btc_eth_max_position_ratio', 5.0)
        self.altcoin_max_ratio = config.get('altcoin_max_position_ratio', 1.0)
        self.min_position_size = config.get('min_position_size', 12.0)
        self.max_margin_usage = config.get('max_margin_usage', 0.9)
        self.min_risk_reward_ratio = config.get('min_risk_reward_ratio', 3.0)
    
    def _is_btc_eth(self, symbol: str) -> bool:
        """
        判断是否为BTC或ETH
        
        Args:
            symbol: 交易对符号
        
        Returns:
            bool: 是否为BTC或ETH
        """
        return symbol in ['BTCUSDT', 'ETHUSDT']
    
    async def check_open_position(
        self,
        symbol: str,
        position_size_usd: float,
        equity: float,
        current_positions: List[Dict[str, Any]],
        tp_price: float,
        sl_price: float,
        entry_price: float,
        direction: str = 'LONG'
    ) -> Tuple[bool, str]:
        """
        检查是否可以开仓（代码级风控，借鉴NOFX）
        
        Args:
            symbol: 交易对符号
            position_size_usd: 仓位大小（USD）
            equity: 账户权益（USD）
            current_positions: 当前仓位列表
            tp_price: 止盈价格
            sl_price: 止损价格
            entry_price: 入场价格
            direction: 方向（LONG/SHORT）
        
        Returns:
            Tuple[bool, str]: (是否可以开仓, 原因)
        """
        try:
            # 1. 检查最大仓位数量
            if len(current_positions) >= self.max_positions:
                return False, f"已达到最大仓位数量: {len(current_positions)}/{self.max_positions}"
            
            # 2. 检查单仓位价值比例（借鉴NOFX）
            if self._is_btc_eth(symbol):
                max_value = equity * self.btc_eth_max_ratio
                ratio_name = f"BTC/ETH ({self.btc_eth_max_ratio}x)"
            else:
                max_value = equity * self.altcoin_max_ratio
                ratio_name = f"Altcoin ({self.altcoin_max_ratio}x)"
            
            if position_size_usd > max_value:
                return False, (
                    f"仓位价值超过限制: ${position_size_usd:.2f} > ${max_value:.2f} "
                    f"(比例: {ratio_name})"
                )
            
            # 3. 检查最小仓位大小
            if position_size_usd < self.min_position_size:
                return False, (
                    f"仓位大小低于最小值: ${position_size_usd:.2f} < ${self.min_position_size:.2f}"
                )
            
            # 4. 检查保证金使用率（借鉴NOFX）
            # 计算当前已使用的保证金
            current_margin = sum(
                p.get('margin', 0) or p.get('position_size_usd', 0)
                for p in current_positions
            )
            total_margin = current_margin + position_size_usd
            margin_usage = total_margin / equity if equity > 0 else 0
            
            if margin_usage > self.max_margin_usage:
                return False, (
                    f"保证金使用率超过限制: {margin_usage:.2%} > {self.max_margin_usage:.2%} "
                    f"(当前: {current_margin:.2f}, 新增: {position_size_usd:.2f}, 总权益: {equity:.2f})"
                )
            
            # 5. 检查风险回报比（借鉴NOFX）
            if entry_price > 0 and tp_price > 0 and sl_price > 0:
                if direction.upper() == 'LONG':
                    risk = abs(entry_price - sl_price)
                    reward = abs(tp_price - entry_price)
                else:  # SHORT
                    risk = abs(sl_price - entry_price)
                    reward = abs(entry_price - tp_price)
                
                if risk > 0:
                    risk_reward_ratio = reward / risk
                    if risk_reward_ratio < self.min_risk_reward_ratio:
                        return False, (
                            f"风险回报比过低: {risk_reward_ratio:.2f}:1 < {self.min_risk_reward_ratio:.2f}:1 "
                            f"(风险: {risk:.2f}, 回报: {reward:.2f})"
                        )
                else:
                    logger.warning(f"风险为0，无法计算风险回报比: {symbol}")
            
            return True, "通过"
        except Exception as e:
            logger.error(f"风控检查失败: {e}", exc_info=True)
            return False, f"风控检查异常: {str(e)}"
    
    async def check_position_risk(
        self,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str, Optional[str]]:
        """
        检查已开仓位的风险（实时监控）
        
        Args:
            position: 仓位信息字典
            current_price: 当前价格
        
        Returns:
            Tuple[bool, str, Optional[str]]: (是否需要风控操作, 风险描述, 建议操作)
        """
        try:
            symbol = position.get('symbol', '')
            side = position.get('side', 'LONG')
            entry_price = float(position.get('entry_price', 0))
            quantity = float(position.get('quantity', 0))
            
            if entry_price <= 0 or quantity <= 0:
                return False, "仓位数据无效", None
            
            # 计算未实现盈亏
            if side == 'LONG':
                unrealized_pnl = (current_price - entry_price) * quantity
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
            else:  # SHORT
                unrealized_pnl = (entry_price - current_price) * quantity
                pnl_pct = ((entry_price - current_price) / entry_price) * 100
            
            # 检查是否需要止损（亏损超过10%）
            if pnl_pct < -10:
                return True, f"亏损超过10%: {pnl_pct:.2f}%", "CLOSE"
            
            # 检查是否需要止盈（盈利超过20%）
            if pnl_pct > 20:
                return True, f"盈利超过20%: {pnl_pct:.2f}%", "REDUCE"
            
            return False, f"未实现盈亏: {unrealized_pnl:.2f} ({pnl_pct:.2f}%)", None
        except Exception as e:
            logger.error(f"仓位风险检查失败: {e}", exc_info=True)
            return False, f"检查异常: {str(e)}", None
    
    def get_config(self) -> Dict[str, Any]:
        """
        获取当前配置
        
        Returns:
            配置字典
        """
        return {
            'max_positions': self.max_positions,
            'btc_eth_max_position_ratio': self.btc_eth_max_ratio,
            'altcoin_max_position_ratio': self.altcoin_max_ratio,
            'min_position_size': self.min_position_size,
            'max_margin_usage': self.max_margin_usage,
            'min_risk_reward_ratio': self.min_risk_reward_ratio
        }
