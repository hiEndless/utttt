import json
from signals.aggregate import compute_all_indicators
from utils.redis_client import get_redis_client, get_batch_writer


def calculate_indicators(klines_data):
    return compute_all_indicators(klines_data)


# -----------------------------
# 指标生成器（写入 Redis）
# -----------------------------
class EventGenerator:
    def __init__(self, symbol: str, kline: list, interval: str):
        self.symbol = symbol
        self.ind = calculate_indicators(kline)
        self.events = []
        self.kline = kline
        self.interval = interval

    async def publish(self, db: int | None = None, use_batch: bool = True):
        """
        发布指标数据到 Redis
        
        Args:
            db: Redis 数据库编号
            use_batch: 是否使用批量写入（默认 True，提高性能）
        """
        indicators_key = f"indicators:binance:{self.symbol}:{self.interval}"
        klines_key = f"klines:binance:{self.symbol}:{self.interval}"
        
        indicators_json = json.dumps(self.ind, ensure_ascii=False)
        klines_json = json.dumps(self.kline, ensure_ascii=False)
        
        if use_batch:
            # 使用批量写入器，支持海量数据瞬时插入
            writer = get_batch_writer(db=db)
            await writer.set(indicators_key, indicators_json)
            await writer.set(klines_key, klines_json)
            
            # 处理前一个周期的指标
            try:
                if isinstance(self.kline, list) and len(self.kline) >= 2:
                    prev_ind = calculate_indicators(self.kline[:-1])
                    prev_key = f"indicators:prev:binance:{self.symbol}:{self.interval}"
                    prev_json = json.dumps(prev_ind, ensure_ascii=False)
                    await writer.set(prev_key, prev_json)
            except Exception:
                pass
        else:
            # 直接写入（用于需要立即生效的场景）
            client = get_redis_client(db)
            await client.set(indicators_key, indicators_json)
            await client.set(klines_key, klines_json)
            try:
                if isinstance(self.kline, list) and len(self.kline) >= 2:
                    prev_ind = calculate_indicators(self.kline[:-1])
                    prev_key = f"indicators:prev:binance:{self.symbol}:{self.interval}"
                    await client.set(prev_key, json.dumps(prev_ind, ensure_ascii=False))
            except Exception:
                pass
        return True


# -----------------------------
# 使用示例
# -----------------------------
if __name__ == "__main__":
    pass
