"""
交易执行模块
将交易决策推送到 Redis，供交易系统执行
"""
import json
import os
from typing import Dict, Any, Optional
import redis.asyncio as aioredis
from agent_server.config import settings


class TradingExecutor:
    """交易执行器"""
    
    def __init__(self):
        # Redis 配置
        self.redis_host = os.getenv("REDIS_HOST", getattr(settings, 'redis_host', '127.0.0.1'))
        self.redis_port = int(os.getenv("REDIS_PORT", getattr(settings, 'redis_port', 6379)))
        self.redis_password = os.getenv("REDIS_PASSWORD", getattr(settings, 'redis_password', None))
        self.redis_db = int(os.getenv("REDIS_DB", getattr(settings, 'redis_db', 1)))
        
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
        
        # 基础交易信息
        trade_json = {
            "order_type": action,  # "open" 或 "close"
            "symbol": symbol,
            "positionSide": decision.get("positionSide", "LONG"),
            "side": decision.get("side", "BUY"),
            "leverage": float(decision.get("leverage", self.default_leverage)),
            "sums": str(decision.get("sums", "0.1")),
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
            "user_id": int(os.getenv("USER_ID", "1")),
            "fast_mode": 1,
            "investment": float(decision.get("investment", self.default_investment)),
            "benchMark": float(decision.get("benchMark", self.default_benchmark)),
            "trade_trigger_mode": 0,
            "sl_trigger_px": float(decision.get("stop_loss_px", 100.0)) if "stop_loss" in decision else 100.0,
            "tp_trigger_px": float(decision.get("take_profit_px", 0.0)) if "take_profit" in decision else 0.0,
            
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

