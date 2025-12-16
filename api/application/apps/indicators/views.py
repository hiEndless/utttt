from fastapi import APIRouter
from pydantic import BaseModel
from dotenv import load_dotenv
from .market_raw_analysis import read_market_raw, build_participant_structure
from .kline_indicators import read_indicators, scan_symbols, read_multi_period
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


class KlineIndicatorsScanRequest(BaseModel):
    exchange: str
    interval: str


@app.post("/kline/indicators/symbols")
async def scan_kline_symbols(req: KlineIndicatorsScanRequest):
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
