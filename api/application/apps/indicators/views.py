from fastapi import APIRouter
from pydantic import BaseModel
from dotenv import load_dotenv
from .market_raw_analysis import read_market_raw, build_participant_structure
from .kline_indicators import read_indicators, scan_symbols, read_multi_period
from .background_kline import read_background, read_multi_period as read_bg_multi_period
from .crowd_state_compactor import read_market_structure as read_crowd_state
from .crowd_state_compactor import scan_symbols as scan_crowd_symbols
from ...common.status_codes import StatusCode
from ...common.redis_client import redis_client

# 加载环境变量
load_dotenv()
app = APIRouter()


class MarketRawRequest(BaseModel):
    exchange: str
    symbol: str


@app.post("/market_raw/analyze")
async def analyze_market_raw(req: MarketRawRequest):
    """分析市场原始数据并构建参与者结构与摘要。
    请求参数：
      - exchange: 交易所名称
      - symbol: 币种符号
    返回：
      - code/msg/data，data 为结构化的参与者画像、ticker 与资金费率分析结果。
    """
    try:
        raw = await read_market_raw(exchange=req.exchange, symbol=req.symbol, client=redis_client)
        analyzed = build_participant_structure(raw, req.symbol)
        return {
            "code": StatusCode.SUCCESS,
            "msg": StatusCode.get_message(StatusCode.SUCCESS),
            "data": analyzed,
        }
    except Exception as e:
        return {
            "code": StatusCode.SERVER_ERROR,
            "msg": f"{StatusCode.get_message(StatusCode.SERVER_ERROR)}: {e}",
        }


class KlineIndicatorsRequest(BaseModel):
    exchange: str
    symbol: str
    interval: str


@app.post("/kline/indicators/read")
async def read_kline_ind(req: KlineIndicatorsRequest):
    """读取指定交易所/币种/周期的技术指标（仅返回指标）。
    请求参数：
      - exchange: 交易所名称
      - symbol: 币种符号
      - interval: 周期（如 1m/5m/1h）
    返回：
      - code/msg/data，data 为指标字典（不包含 prev_indicators/klines）。
    """
    try:
        data = await read_indicators(req.exchange, req.symbol, req.interval, redis_client)
        return {
            "code": StatusCode.SUCCESS,
            "msg": StatusCode.get_message(StatusCode.SUCCESS),
            "data": data,
        }
    except Exception as e:
        return {
            "code": StatusCode.SERVER_ERROR,
            "msg": f"{StatusCode.get_message(StatusCode.SERVER_ERROR)}: {e}",
        }


class CrowdStateRequest(BaseModel):
    exchange: str
    symbol: str


@app.post("/crowd_state/read")
async def read_crowd_state_view(req: CrowdStateRequest):
    """读取指定交易所/币种的 crowd/market_structure 背景。
    请求参数：
      - exchange: 交易所名称
      - symbol: 币种符号
    返回：
      - code/msg/data，data 为 market_structure 的字典。
    """
    try:
        data = await read_crowd_state(req.exchange, req.symbol, redis_client)
        return {
            "code": StatusCode.SUCCESS,
            "msg": StatusCode.get_message(StatusCode.SUCCESS),
            "data": data,
        }
    except Exception as e:
        return {
            "code": StatusCode.SERVER_ERROR,
            "msg": f"{StatusCode.get_message(StatusCode.SERVER_ERROR)}: {e}",
        }


class CrowdStateScanRequest(BaseModel):
    exchange: str


@app.post("/crowd_state/symbols")
async def scan_crowd_state_symbols(req: CrowdStateScanRequest):
    """扫描指定交易所下存在 crowd/market_structure 背景的符号列表。
    请求参数：
      - exchange: 交易所名称
    返回：
      - code/msg/data，data.symbols 为可用的 symbol 列表。
    """
    try:
        symbols = await scan_crowd_symbols(req.exchange, redis_client)
        return {
            "code": StatusCode.SUCCESS,
            "msg": StatusCode.get_message(StatusCode.SUCCESS),
            "data": {"symbols": symbols},
        }
    except Exception as e:
        return {
            "code": StatusCode.SERVER_ERROR,
            "msg": f"{StatusCode.get_message(StatusCode.SERVER_ERROR)}: {e}",
        }


class KlineIndicatorsScanRequest(BaseModel):
    exchange: str
    interval: str


@app.post("/kline/indicators/symbols")
async def scan_kline_symbols(req: KlineIndicatorsScanRequest):
    """扫描指定交易所与周期下存在指标数据的符号列表。
    请求参数：
      - exchange: 交易所名称
      - interval: 周期
    返回：
      - code/msg/data，data.symbols 为可用的 symbol 列表。
    """
    try:
        symbols = await scan_symbols(req.exchange, req.interval, redis_client)
        return {
            "code": StatusCode.SUCCESS,
            "msg": StatusCode.get_message(StatusCode.SUCCESS),
            "data": {"symbols": symbols},
        }
    except Exception as e:
        return {
            "code": StatusCode.SERVER_ERROR,
            "msg": f"{StatusCode.get_message(StatusCode.SERVER_ERROR)}: {e}",
        }


class KlineIndicatorsMultiPeriodRequest(BaseModel):
    exchange: str
    symbol: str
    intervals: list[str]


@app.post("/kline/indicators/read_multi")
async def read_kline_multi(req: KlineIndicatorsMultiPeriodRequest):
    """批量读取多周期的技术指标。
    请求参数：
      - exchange: 交易所名称
      - symbol: 币种符号
      - intervals: 周期列表（如 ["1m","5m","1h"]）
    返回：
      - code/msg/data，data 为 {interval: 指标字典} 映射。
    """
    try:
        data = await read_multi_period(req.exchange, req.symbol, req.intervals, redis_client)
        return {
            "code": StatusCode.SUCCESS,
            "msg": StatusCode.get_message(StatusCode.SUCCESS),
            "data": data,
        }
    except Exception as e:
        return {
            "code": StatusCode.SERVER_ERROR,
            "msg": f"{StatusCode.get_message(StatusCode.SERVER_ERROR)}: {e}",
        }


class BackgroundKlineRequest(BaseModel):
    exchange: str
    symbol: str
    interval: str


@app.post("/kline/background/read")
async def read_background_kline(req: BackgroundKlineRequest):
    """读取指定交易所/币种/周期的背景K线指标（仅返回背景数据）。
    请求参数：
      - exchange: 交易所名称
      - symbol: 币种符号
      - interval: 周期（如 1m/5m/1h）
    返回：
      - code/msg/data，data 为背景指标字典。
    """
    try:
        data = await read_background(req.exchange, req.symbol, req.interval, redis_client)
        return {
            "code": StatusCode.SUCCESS,
            "msg": StatusCode.get_message(StatusCode.SUCCESS),
            "data": data,
        }
    except Exception as e:
        return {
            "code": StatusCode.SERVER_ERROR,
            "msg": f"{StatusCode.get_message(StatusCode.SERVER_ERROR)}: {e}",
        }


class BackgroundKlineMultiPeriodRequest(BaseModel):
    exchange: str
    symbol: str
    intervals: list[str]


@app.post("/kline/background/read_multi")
async def read_background_multi(req: BackgroundKlineMultiPeriodRequest):
    """批量读取多周期的背景K线指标。
    请求参数：
      - exchange: 交易所名称
      - symbol: 币种符号
      - intervals: 周期列表（如 ["1m","5m","1h"]）
    返回：
      - code/msg/data，data 为 {interval: 背景指标字典} 映射。
    """
    try:
        data = await read_bg_multi_period(req.exchange, req.symbol, req.intervals, redis_client)
        return {
            "code": StatusCode.SUCCESS,
            "msg": StatusCode.get_message(StatusCode.SUCCESS),
            "data": data,
        }
    except Exception as e:
        return {
            "code": StatusCode.SERVER_ERROR,
            "msg": f"{StatusCode.get_message(StatusCode.SERVER_ERROR)}: {e}",
        }
