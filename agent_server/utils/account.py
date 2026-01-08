import json
from agent_server.utils.redis_client import RedisClient


async def get_available_exposure_pct(exchange: str) -> float:
    """
    根据账户余额从 Redis 获取可用敞口百分比。
    计算公式：availableBalance / balance
    
    参数：
        exchange (str): 交易所名称（例如 'binance'）
        
    返回：
        float: 计算得出的可用敞口百分比（失败时默认为 0.12）
    """
    rc = RedisClient()
    balance_key = f"balance:{exchange}"
    balance_str = await rc.get(balance_key)
    calculated_available_pct = 0.12  # 默认后备值

    if balance_str:
        try:
            balance_data = json.loads(balance_str)
            total_balance = float(balance_data.get("balance", 0))
            avail_balance = float(balance_data.get("availableBalance", 0))
            if total_balance > 0:
                calculated_available_pct = avail_balance / total_balance
        except Exception as e:
            print(f"Error calculating available exposure: {e}")

    return calculated_available_pct


if __name__ == "__main__":
    import asyncio
    available_pct = asyncio.run(get_available_exposure_pct("binance"))
    print(available_pct)
