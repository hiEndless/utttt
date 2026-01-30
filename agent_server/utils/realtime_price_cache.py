"""
实时价格缓存（借鉴NOFX多级缓存机制）
在内存中维护最新价格缓存，减少Redis读取次数，提升性能
"""

from collections import defaultdict
import time
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # 减少日志噪音


class PriceCache:
    """实时价格缓存（借鉴NOFX）"""
    
    def __init__(self, ttl=5.0):
        """
        初始化价格缓存
        
        Args:
            ttl: 缓存生存时间（秒），默认5秒
        """
        self.cache = defaultdict(dict)
        self.ttl = ttl  # 5秒TTL
    
    def get_price(self, exchange, symbol):
        """
        获取价格，如果过期返回None
        
        Args:
            exchange: 交易所名称（如 'binance'）
            symbol: 交易对符号（如 'BTCUSDT'）
        
        Returns:
            价格（float）或 None（如果缓存不存在或已过期）
        """
        if symbol in self.cache[exchange]:
            price_data = self.cache[exchange][symbol]
            age = time.time() - price_data['timestamp']
            if age < self.ttl:
                return price_data['price']
            else:
                # 过期，删除
                del self.cache[exchange][symbol]
                logger.debug(f"价格缓存过期: {exchange}:{symbol} (age: {age:.2f}s)")
        return None
    
    def set_price(self, exchange, symbol, price):
        """
        更新价格
        
        Args:
            exchange: 交易所名称
            symbol: 交易对符号
            price: 价格值
        """
        self.cache[exchange][symbol] = {
            'price': float(price),
            'timestamp': time.time()
        }
        logger.debug(f"更新价格缓存: {exchange}:{symbol} = {price}")
    
    def is_stale(self, exchange, symbol):
        """
        检查价格是否过期
        
        Args:
            exchange: 交易所名称
            symbol: 交易对符号
        
        Returns:
            True 如果缓存不存在或已过期，False 如果缓存有效
        """
        if symbol not in self.cache[exchange]:
            return True
        age = time.time() - self.cache[exchange][symbol]['timestamp']
        return age > self.ttl
    
    def clear(self, exchange=None, symbol=None):
        """
        清理缓存
        
        Args:
            exchange: 交易所名称，如果为None则清理所有交易所
            symbol: 交易对符号，如果为None则清理该交易所的所有交易对
        """
        if exchange and symbol:
            if symbol in self.cache[exchange]:
                del self.cache[exchange][symbol]
                logger.debug(f"清理价格缓存: {exchange}:{symbol}")
        elif exchange:
            self.cache[exchange].clear()
            logger.debug(f"清理交易所缓存: {exchange}")
        else:
            self.cache.clear()
            logger.debug("清理所有价格缓存")
    
    def get_cache_info(self, exchange=None):
        """
        获取缓存信息（用于调试）
        
        Args:
            exchange: 交易所名称，如果为None则返回所有交易所的信息
        
        Returns:
            缓存信息字典
        """
        if exchange:
            symbols = list(self.cache[exchange].keys())
            return {
                'exchange': exchange,
                'symbol_count': len(symbols),
                'symbols': symbols
            }
        else:
            return {
                'exchanges': list(self.cache.keys()),
                'total_symbols': sum(len(symbols) for symbols in self.cache.values())
            }


# 全局实例
_price_cache = PriceCache()


def get_price_cache():
    """
    获取全局价格缓存实例
    
    Returns:
        PriceCache 实例
    """
    return _price_cache
