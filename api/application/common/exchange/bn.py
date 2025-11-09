import requests
from ..signals.bollingerband import BollingerBandSignal
from ..signals.ma import MA
from ..signals.rsi import RSI
from ..signals.macd import MACD
from ..signals.kdj import KDJ
from ..signals.support_resistance import SupportResistance
from ..signals.volatility import VolatilitySignal
from ..proxies import proxies
import random
# 【新增】导入新方法所需的库
import time
import json
import logging
from datetime import datetime, timedelta, timezone

# from api.application.common.signals.bollingerband import BollingerBandSignal
# from api.application.common.signals.ma import MA
# from api.application.common.signals.rsi import RSI
# from api.application.common.signals.macd import MACD
# from api.application.common.signals.kdj import KDJ
# from api.application.common.signals.support_resistance import SupportResistance
# from api.application.common.signals.volatility import VolatilitySignal
# from api.application.common.proxies import proxies

logger = logging.getLogger(__name__)

class BnClient:
    def __init__(self):
        self.baseUrl = 'https://fapi.binance.com'
        self.proxy = random.choice(proxies)
        # self.proxy = {}

    # --- 【新增】健壮的历史价格获取方法 (双重策略) ---
    def get_historical_price(self, symbol: str, timestamp: datetime) -> float:
        """
        获取历史价格的健壮方法（双重策略）。

        1. 优先尝试使用 aggTrades 进行秒级精确追溯。
        2. 如果 aggTrades 失败，则自动回退到获取1分钟K线的收盘价。
        """
        # 策略一：尝试秒级精度的 aggTrades
        price = self._get_price_from_agg_trades_with_lookback(symbol, timestamp)
        if price > 0:
            return price

        # 策略二：如果上面失败，回退到分钟级K线
        logger.warning(f"秒级价格获取失败，回退至分钟级K线价格获取策略 (Symbol: {symbol}, Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')})")
        price = self._get_price_from_klines_fallback(symbol, timestamp)

        if price == 0.0:
            logger.error(f"所有策略均失败，无法获取 {symbol} 在 {timestamp.strftime('%Y-%m-%d %H:%M:%S')} 附近的任何有效价格。")

        return price

    def _get_price_from_agg_trades_with_lookback(self, symbol: str, timestamp: datetime) -> float:
        """
        内部辅助方法：通过查询历史归集交易，获取最接近指定时间戳的成交价（带追溯）。
        """
        # 注意：适配合约API的URL
        url = self.baseUrl + '/fapi/v1/aggTrades'
        max_lookback_seconds = 60
        retries_per_request = 3
        delay_between_retries = 3

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        for seconds_ago in range(max_lookback_seconds):
            current_timestamp = timestamp - timedelta(seconds=seconds_ago)
            start_time_ms = int(current_timestamp.timestamp() * 1000)
            end_time_ms = start_time_ms + 999

            params = {'symbol': symbol, 'startTime': start_time_ms, 'endTime': end_time_ms}

            for attempt in range(retries_per_request):
                try:
                    response = requests.get(url, params=params, timeout=10, proxies=self.proxy)
                    response.raise_for_status()
                    agg_trades = response.json()

                    if agg_trades and len(agg_trades) > 0:
                        trade_price = float(agg_trades[-1]['p'])
                        trade_time = datetime.fromtimestamp(int(agg_trades[-1]['T']) / 1000, tz=timezone.utc)
                        log_message = f"成功通过[aggTrades]获取 {symbol} 在 {timestamp.strftime('%Y-%m-%d %H:%M:%S')} 的历史价格: {trade_price}"
                        if seconds_ago > 0:
                            log_message += f" (向前追溯了 {seconds_ago} 秒, 实际成交时间: {trade_time.strftime('%Y-%m-%d %H:%M:%S')})"
                        logger.info(log_message)
                        return trade_price
                    else:
                        if seconds_ago < 5:
                            logger.debug(f"在 {current_timestamp.strftime('%Y-%m-%d %H:%M:%S')} 无成交记录，继续向前追溯...")
                        break

                except (requests.exceptions.RequestException, json.JSONDecodeError, IndexError) as e:
                    logger.warning(f"从 aggTrades 获取 {symbol} 价格失败 (尝试 {attempt + 1}/{retries_per_request}): {e}")
                    if attempt < retries_per_request - 1:
                        time.sleep(delay_between_retries)
        return 0.0

    def _get_price_from_klines_fallback(self, symbol: str, timestamp: datetime) -> float:
        """
        内部辅助方法：通过查询1分钟K线获取指定时间点的收盘价（作为回退策略）。
        """
        url = self.baseUrl + '/fapi/v1/klines'

        kline_start_time_ms = int(timestamp.replace(second=0, microsecond=0).timestamp() * 1000)

        params = {
            'symbol': symbol,
            'interval': '1m',
            'startTime': kline_start_time_ms,
            'limit': 1
        }
        try:
            response = requests.get(url, params=params, timeout=10, proxies=self.proxy)
            response.raise_for_status()
            kline_data = response.json()
            if kline_data and len(kline_data) > 0:
                close_price = float(kline_data[0][4])
                logger.info(f"成功通过[Klines Fallback]获取 {symbol} 在 {timestamp.strftime('%Y-%m-%d %H:%M')} 分钟的收盘价: {close_price}")
                return close_price
        except (requests.exceptions.RequestException, json.JSONDecodeError, IndexError) as e:
            logger.error(f"从 Klines Fallback 获取 {symbol} 价格失败: {e}")

        return 0.0
    # --- 新增方法结束 ---


    def premiumIndex(self, symbol, *args, **kwargs):
        url = self.baseUrl + '/fapi/v1/premiumIndex'
        params = {
            'symbol': symbol
        }
        response = requests.get(url, params=params, timeout=10, proxies=self.proxy).json()
        markPrice = response.get('markPrice')
        FundingRate = response.get('lastFundingRate')
        return {
            'markPrice': markPrice,
            'FundingRate': FundingRate
        }

    def ticker24hr(self, symbol,  *args, **kwargs):
        url = self.baseUrl + '/fapi/v1/ticker/24hr'
        params = {
            'symbol': symbol
        }
        response = requests.get(url, params=params, timeout=10, proxies=self.proxy).json()
        priceChangePercent = response.get('priceChangePercent')
        volume = response.get('volume')
        quoteVolume = response.get('quoteVolume')
        return {
            'priceChangePercent': priceChangePercent,
            'volume': volume,
            'quoteVolume': quoteVolume
        }

    def takerlongshortRatio(self, symbol: str, period: str):
        url = self.baseUrl + '/futures/data/takerlongshortRatio'
        if period == '10m':
            period = '5m'
        params = {
            'symbol': symbol,
            'period': period,
            'limit': 1
        }
        response = requests.get(url, params=params, timeout=10, proxies=self.proxy).json()
        buySellRatio = response[0]['buySellRatio']
        buyVol = float(response[0]['buyVol'])
        sellVol = float(response[0]['sellVol'])
        buyRatio = buyVol / (buyVol + sellVol)
        sellRatio = sellVol / (buyVol + sellVol)
        return {
            'buySellRatio': buySellRatio,
            # 'buyVol': buyVol,
            # 'sellVol': sellVol,
            'buyRatio': buyRatio,
            'sellRatio': sellRatio
        }

    def globalLongShortAccountRatio(self, symbol: str, period: str):
        url = self.baseUrl + '/futures/data/globalLongShortAccountRatio'
        if period == '10m':
            period = '5m'
        params = {
            'symbol': symbol,
            'period': period,
            'limit': 1
        }
        response = requests.get(url, params=params, timeout=10, proxies=self.proxy).json()
        longShortRatio = response[0]['longShortRatio']
        longAccount = response[0]['longAccount']
        shortAccount = response[0]['shortAccount']
        return {
            'longShortRatio': longShortRatio,
            'longAccount': longAccount,
            'shortAccount': shortAccount
        }

    def topLongShortPositionRatio(self, symbol: str, period: str):
        """大户持仓"""
        url = self.baseUrl + '/futures/data/topLongShortPositionRatio'
        if period == '10m':
            period = '5m'
        params = {
            'symbol': symbol,
            'period': period,
            'limit': 1
        }
        response = requests.get(url, params=params, timeout=10, proxies=self.proxy).json()
        longShortRatio = response[0]['longShortRatio']
        longAccount = response[0]['longAccount']
        shortAccount = response[0]['shortAccount']
        return {
            'longShortRatio': longShortRatio,
            'longAccount': longAccount,
            'shortAccount': shortAccount
        }

    def topLongShortAccountRatio(self, symbol: str, period: str):
        """大户账户"""
        url = self.baseUrl + '/futures/data/topLongShortAccountRatio'
        if period == '10m':
            period = '5m'
        params = {
            'symbol': symbol,
            'period': period,
            'limit': 1
        }
        response = requests.get(url, params=params, timeout=10, proxies=self.proxy).json()
        longShortRatio = response[0]['longShortRatio']
        longAccount = response[0]['longAccount']
        shortAccount = response[0]['shortAccount']
        return {
            'longShortRatio': longShortRatio,
            'longAccount': longAccount,
            'shortAccount': shortAccount
        }

    def klines(self, symbol: str, interval: str, limit: int = 200):
        url = self.baseUrl + '/fapi/v1/klines'
        if interval == '10m':
            interval = '5m'
        params = {
            'symbol': symbol,
            'contractType': 'PERPETUAL',
            'interval': interval,
            'limit': limit
        }
        response = requests.get(url, params=params, timeout=10, proxies=self.proxy).json()
        return response

    def signals(self, symbol: str, interval: str, limit: int = 400):
        klines_data = self.klines(symbol, interval, limit)
        bolling = BollingerBandSignal(klines_data).calculate()
        ma = MA(klines_data).calculate()
        rsi = RSI(klines_data).calculate()
        macd = MACD(klines_data).calculate()
        kdj = KDJ(klines_data).calculate()
        support_resistance = SupportResistance(klines_data).calculate()
        volatility = VolatilitySignal(klines_data).calculate()
        return bolling, ma, rsi, macd, kdj, support_resistance, volatility, klines_data


if __name__ == '__main__':
    bn = BnClient()
    bolling, ma, rsi, macd, kdj, support_resistance, volatility, klines_data = bn.signals('BTCUSDT', '1d')
    print(volatility)