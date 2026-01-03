"""
交易执行模块
将交易决策推送到 Redis，供交易系统执行
"""
import json
import os
from typing import Dict, Any, Optional
from decimal import Decimal, ROUND_DOWN, ROUND_UP
import redis.asyncio as aioredis
from agent_server.config import settings


class TradingExecutor:
    """交易执行器"""
    
    def __init__(self):
        # 交易任务 Redis 配置（优先使用环境变量，否则使用配置中的交易 Redis 配置）
        self.redis_host = os.getenv("TRADE_REDIS_HOST") or getattr(settings, 'trade_redis_host', '101.32.115.249')
        self.redis_port = int(os.getenv("TRADE_REDIS_PORT") or getattr(settings, 'trade_redis_port', 6379))
        self.redis_password = os.getenv("TRADE_REDIS_PASSWORD") or getattr(settings, 'trade_redis_password', 'liu146015')
        self.redis_db = int(os.getenv("TRADE_REDIS_DB") or getattr(settings, 'trade_redis_db', 1))
        
        # 交易任务队列 key
        self.trade_task_key = os.getenv("TRADE_TASK_KEY", "TASK_ADD_TRADE")
        
        # 交易配置（从环境变量或配置读取）
        self.default_leverage = float(os.getenv("DEFAULT_LEVERAGE", "5.0"))
        self.default_investment = float(os.getenv("DEFAULT_INVESTMENT", "100.0"))
        self.default_benchmark = float(os.getenv("DEFAULT_BENCHMARK", "100.0"))
        self.trader_platform = int(os.getenv("TRADER_PLATFORM", "2"))  # 2=币安
        self.api_config = self._load_api_config()
        
        self.redis: Optional[aioredis.Redis] = None
    
    def _load_api_config(self) -> Dict:
        """加载 API 配置"""
        return {
            "key": os.getenv("BINANCE_API_KEY", ""),
            "secret": os.getenv("BINANCE_API_SECRET", ""),
            "passphrase": os.getenv("BINANCE_PASSPHRASE", ""),
            "exchange": 2,  # 币安
            "proxies": {}  # 代理配置（如果需要）
        }
    
    def _get_symbol_step_size(self, symbol: str) -> float:
        """
        获取交易对的步长（stepSize）
        
        常见币种的默认精度：
        - BTCUSDT, ETHUSDT: 0.001 (3位小数)
        - BEATUSDT, 大多数山寨币: 0.01 (2位小数) 或 0.001 (3位小数)
        - 小币种: 0.1 (1位小数) 或 1 (整数)
        
        Args:
            symbol: 交易对
            
        Returns:
            stepSize (默认 0.01，适用于大多数币种)
        """
        # 常见币种的精度映射（可以根据实际情况扩展）
        precision_map = {
            "BTCUSDT": 0.001,
            "ETHUSDT": 0.001,
            "BNBUSDT": 0.001,
            "SOLUSDT": 0.01,
            "ADAUSDT": 0.1,
            "DOGEUSDT": 1.0,
            "BEATUSDT": 1.0,  # BEATUSDT 使用整数精度（根据币安API错误信息调整）
        }
        
        # 如果币种在映射中，使用映射值
        if symbol in precision_map:
            return precision_map[symbol]
        
        # 默认使用 0.01 (2位小数)，适用于大多数币种
        # 如果遇到精度错误，可以调整为 0.001 或 0.1 或 1.0
        return 0.01
    
    def _format_quantity(self, quantity: Any, symbol: str, order_type: str = "open") -> str:
        """
        格式化交易数量，符合币安精度要求
        
        Args:
            quantity: 原始数量（可以是字符串、float、int）
            symbol: 交易对
            order_type: 订单类型 ("open", "close", "reduce")
            
        Returns:
            格式化后的数量字符串
        """
        try:
            # 获取步长
            step_size = self._get_symbol_step_size(symbol)
            
            # 转换为 Decimal 进行精确计算
            if isinstance(quantity, str):
                quantity_decimal = Decimal(quantity)
            else:
                quantity_decimal = Decimal(str(float(quantity)))
            
            # 计算小数位数
            step_decimal = Decimal(str(step_size))
            step_str = str(step_size)
            
            # 计算小数位数（从 stepSize 中提取）
            if '.' in step_str:
                decimal_places = len(step_str.split('.')[-1].rstrip('0'))
            else:
                decimal_places = 0
            
            # 根据订单类型选择舍入方式
            # 开仓：向下取整（避免超过可用资金）
            # 平仓/减仓：向上取整（确保完全平仓）
            rounding = ROUND_DOWN if order_type == "open" else ROUND_UP
            
            # 将数量对齐到步长
            quantize_exp = Decimal('0.' + '0' * (decimal_places - 1) + '1') if decimal_places > 0 else Decimal('1')
            rounded_quantity = quantity_decimal.quantize(quantize_exp, rounding=rounding)
            
            # 确保数量是 stepSize 的倍数
            if step_size < 1:
                # 对于小数步长，需要对齐
                rounded_quantity = (rounded_quantity // step_decimal) * step_decimal
                # 再次量化到正确的小数位数
                rounded_quantity = rounded_quantity.quantize(quantize_exp, rounding=rounding)
            
            # 检查格式化后的数量是否为 0
            # 如果为 0，使用向上取整确保至少为最小交易量
            if rounded_quantity <= 0:
                print(f"⚠️  警告：格式化后数量为 0，使用向上取整")
                # 使用向上取整，至少为 stepSize
                rounded_quantity = step_decimal
                rounded_quantity = rounded_quantity.quantize(quantize_exp, rounding=ROUND_UP)
            
            # 转换为字符串
            result_str = str(rounded_quantity)
            
            # 如果 stepSize 是整数（1.0），则返回整数格式
            if decimal_places == 0:
                # 移除小数点
                if '.' in result_str:
                    result_str = result_str.split('.')[0]
                return result_str
            
            # 对于小数精度，确保格式正确
            if '.' in result_str:
                parts = result_str.split('.')
                integer_part = parts[0]
                decimal_part = parts[1].rstrip('0')  # 移除尾随零
                
                # 如果小数部分为空，但需要保留精度，则补零
                if len(decimal_part) == 0 and decimal_places > 0:
                    decimal_part = '0' * decimal_places
                elif len(decimal_part) < decimal_places:
                    # 补齐到所需精度
                    decimal_part = decimal_part + '0' * (decimal_places - len(decimal_part))
                
                result_str = f"{integer_part}.{decimal_part}" if decimal_part else integer_part
            else:
                # 如果没有小数点，但需要小数精度，则添加
                if decimal_places > 0:
                    result_str = result_str + '.' + '0' * decimal_places
            
            return result_str
            
        except Exception as e:
            print(f"⚠️  格式化数量失败: {e}, 使用原始值")
            return str(quantity)
    
    async def _get_redis(self) -> aioredis.Redis:
        """获取 Redis 连接"""
        if self.redis is None:
            self.redis = aioredis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                db=self.redis_db,
                decode_responses=True
            )
        return self.redis
    
    def _validate_decision(self, decision: Dict) -> bool:
        """
        验证决策格式
        
        Args:
            decision: 交易决策字典
            
        Returns:
            是否有效
        """
        required_fields = ["action", "symbol"]
        
        # 检查必需字段
        for field in required_fields:
            if field not in decision:
                print(f"❌ 决策缺少必需字段: {field}")
                return False
        
        action = decision.get("action")
        
        # 如果是开仓或平仓，检查交易相关字段
        if action in ("open", "close"):
            required_trade_fields = ["positionSide", "side", "sums", "openAvgPx"]
            for field in required_trade_fields:
                if field not in decision:
                    print(f"❌ 交易决策缺少必需字段: {field}")
                    return False
        
        # 检查置信度
        confidence = float(decision.get("confidence", 0.0))
        if action in ("open", "close") and confidence < 0.6:
            print(f"⚠️  置信度过低 ({confidence:.2f})，不执行交易")
            return False
        
        return True
    
    def _build_trade_json(self, decision: Dict) -> Dict:
        """
        构建币安交易 JSON 格式
        
        参考: BINANCE_REDIS_JSON_STRUCTURE.md
        """
        action = decision.get("action")
        symbol = decision.get("symbol", "BTCUSDT")
        
        # 格式化数量（符合币安精度要求）
        raw_sums = decision.get("sums", "0.1")
        formatted_sums = self._format_quantity(raw_sums, symbol, action)
        
        # 基础交易信息
        trade_json = {
            "order_type": action,  # "open" 或 "close"
            "symbol": symbol,
            "positionSide": decision.get("positionSide", "LONG"),
            "side": decision.get("side", "BUY"),
            "leverage": float(decision.get("leverage", self.default_leverage)),
            "sums": formatted_sums,  # 使用格式化后的数量
            "openAvgPx": float(decision.get("openAvgPx", 0.0)),
            
            # 任务配置
            "task_id": 0,  # AI 系统任务ID
            "trader_platform": self.trader_platform,
            "follow_type": 2,
            "uniqueName": "ai_trading_system",
            "role_type": 1,
            "reduce_ratio": 0.0,
            "multiple": 1.0,
            "ratio": 0.0,
            "lever_set": 1,
            "first_order_set": 1,
            "api_id": int(os.getenv("API_ID", "0")),
            "user_id": int(os.getenv("TRADE_USER_ID") or getattr(settings, 'trade_user_id', 2)),
            "fast_mode": 1,
            "investment": float(decision.get("investment", self.default_investment)),
            "benchMark": float(decision.get("benchMark", self.default_benchmark)),
            "trade_trigger_mode": 0,
            "sl_trigger_px": float(decision.get("stop_loss") or decision.get("stop_loss_px") or 100.0) if (decision.get("stop_loss") or decision.get("stop_loss_px")) else 100.0,
            "tp_trigger_px": float(decision.get("take_profit") or decision.get("take_profit_px") or 0.0) if (decision.get("take_profit") or decision.get("take_profit_px")) else 0.0,
            
            # API 配置
            "acc": self.api_config,
            
            # 其他配置
            "flag": os.getenv("TRADE_FLAG", "1"),  # "0"=实盘, "1"=模拟盘
            "ip_id": int(os.getenv("IP_ID", "1")),
            "posSide_set": 1,
            "pos_mode": 0,
            "pos_value": decision.get("positionSide", "LONG").lower(),
            "vol24h_mode": 0,
            "vol24h_num": 10,
            "white_list_mode": 0,
            "white_list": [],
            "black_list_mode": 0,
            "black_list": [],
            "balance_monitor_mode": 0,
            "balance_monitor_value": 1000.0,
            "private_set": 0,
        }
        
        return trade_json
    
    async def execute_trade(self, decision: Dict) -> Dict[str, Any]:
        """
        执行交易推送
        
        Args:
            decision: 交易决策字典
            
        Returns:
            执行结果
        """
        try:
            # 验证决策
            if not self._validate_decision(decision):
                return {
                    "success": False,
                    "action": decision.get("action", "unknown"),
                    "reason": "决策验证失败"
                }
            
            action = decision.get("action")
            
            # 如果是保持不动，不推送
            if action == "hold":
                return {
                    "success": True,
                    "action": "hold",
                    "message": "保持不动，不执行交易",
                    "pushed": False
                }
            
            # 构建交易 JSON
            trade_json = self._build_trade_json(decision)
            
            # 推送到 Redis
            redis = await self._get_redis()
            await redis.lpush(
                self.trade_task_key,
                json.dumps(trade_json, ensure_ascii=False)
            )
            
            print(f"✅ 交易决策已推送到 Redis: {self.trade_task_key}")
            print(f"   动作: {action}")
            print(f"   交易对: {trade_json['symbol']}")
            print(f"   方向: {trade_json['positionSide']} {trade_json['side']}")
            print(f"   数量: {trade_json['sums']}")
            print(f"   价格: {trade_json['openAvgPx']}")
            
            return {
                "success": True,
                "action": action,
                "pushed": True,
                "trade_json": trade_json,
                "redis_key": self.trade_task_key
            }
            
        except Exception as e:
            print(f"❌ 执行交易失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "action": decision.get("action", "unknown"),
                "error": str(e)
            }
    
    async def close(self):
        """关闭 Redis 连接"""
        if self.redis:
            await self.redis.aclose()
            self.redis = None


# 全局实例
_executor_instance: Optional[TradingExecutor] = None


async def get_executor() -> TradingExecutor:
    """获取全局执行器实例"""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = TradingExecutor()
    return _executor_instance

