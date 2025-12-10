from fastapi import APIRouter
from pydantic import BaseModel
from dotenv import load_dotenv
from .market_raw_analysis import read_market_raw, build_participant_structure
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


