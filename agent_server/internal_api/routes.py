from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from agent_server.agent_context.builder import build_agent_context
from agent_server.agent_context.market_structure.io.background_kline import DEFAULT_INTERVALS
from agent_server.agent_context.market_structure import output as market_output
from agent_server.agents.experts.background.kline import KLineExpert
from agent_server.agent_workflow.signal_validation_workflow import SignalValidationWorkflow
from agent_server.agent_workflow.trade_event_workflow import TradeEventWorkflow
from agent_server.config import settings
from agent_server.internal_api.auth import verify_internal_token
from agent_server.internal_api.schemas import (
    BuildContextRequest,
    RefreshKlineRequest,
    RefreshMarketStateRequest,
    WorkflowRunRequest,
)
from agent_server.utils.http_client import http_client
from agent_server.utils.redis_client import RedisClient


router = APIRouter(prefix="/internal", tags=["internal-agent"])


@router.get("/healthz", dependencies=[Depends(verify_internal_token)])
async def healthz() -> Dict[str, Any]:
    return {"ok": True, "service": "agent_server_internal_api", "ts": int(time.time() * 1000)}


async def _read_market_state(exchange: str, symbol: str) -> Dict[str, Any]:
    rc = RedisClient()
    key = f"background:{exchange}:{symbol}:market_state"
    raw = await rc.get(key)
    try:
        return json.loads(raw or "{}") if raw else {}
    except Exception:
        return {}


async def _fetch_kline_indicators(exchange: str, symbol: str, interval: str) -> Dict[str, Any]:
    base = str(settings.api_base_url or "").rstrip("/")
    if not base:
        raise RuntimeError("API_BASE_URL not configured")
    url = base + "/kline/indicators/read"
    payload = {"exchange": exchange, "symbol": symbol, "interval": interval}
    res = await http_client.request("POST", url, json=payload)
    if not isinstance(res, dict):
        raise RuntimeError(f"bad_response_type={type(res).__name__}")
    if "data" not in res:
        raise RuntimeError(f"no_data_field res={res}")
    data = res.get("data")
    if data is None:
        raise RuntimeError(f"data_none code={res.get('code')} msg={res.get('msg')}")
    if not isinstance(data, dict):
        raise RuntimeError(f"bad_data_type={type(data).__name__}")
    return data


@router.post("/refresh/kline", dependencies=[Depends(verify_internal_token)])
async def refresh_kline(req: RefreshKlineRequest) -> Dict[str, Any]:
    exchange = str(req.exchange or "binance")
    symbol = str(req.symbol or "").strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol_required")

    intervals = [str(x).strip() for x in (req.intervals or DEFAULT_INTERVALS) if str(x).strip()]
    if not intervals:
        raise HTTPException(status_code=400, detail="intervals_required")

    sem = asyncio.Semaphore(int(req.max_concurrency or 2))
    expert = KLineExpert()

    async def _run_one(itv: str) -> Dict[str, Any]:
        async with sem:
            try:
                indicators = await _fetch_kline_indicators(exchange, symbol, itv)
                query = {"interval": itv, "symbol": symbol}
                query.update(indicators)
                raw = await expert.run(query, exchange, symbol)
                try:
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    parsed = {"raw": raw}
                return {"ok": True, "interval": itv, "result": parsed}
            except Exception as e:
                return {"ok": False, "interval": itv, "error": str(e)}

    results = await asyncio.gather(*[_run_one(itv) for itv in intervals])
    by_interval: Dict[str, Any] = {r.get("interval"): r for r in results if isinstance(r, dict) and r.get("interval")}
    return {"exchange": exchange, "symbol": symbol, "intervals": intervals, "results": by_interval, "ts": int(time.time() * 1000)}


@router.post("/refresh/market_state", dependencies=[Depends(verify_internal_token)])
async def refresh_market_state(req: RefreshMarketStateRequest) -> Dict[str, Any]:
    exchange = str(req.exchange or "binance")
    symbol = str(req.symbol or "").strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol_required")
    out = await market_output.build_output(exchange, symbol)
    return {"ok": True, "exchange": exchange, "symbol": symbol, "market_state": out, "ts": int(time.time() * 1000)}


@router.post("/context/build", dependencies=[Depends(verify_internal_token)])
async def build_context(req: BuildContextRequest) -> Dict[str, Any]:
    agent = str(req.agent or "").strip()
    if not agent:
        raise HTTPException(status_code=400, detail="agent_required")
    exchange = str(req.exchange or "binance")
    symbol = str(req.symbol or "").strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol_required")
    full_context = await _read_market_state(exchange, symbol)
    ctx = build_agent_context(agent, full_context, horizon=req.horizon)
    return {"ok": True, "agent": agent, "exchange": exchange, "symbol": symbol, "context": ctx, "ts": int(time.time() * 1000)}


def _try_parse_json(val: Any) -> Any:
    if isinstance(val, dict) or isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {"raw": val}
    return {"raw": val}


@router.post("/workflow/signal_validation", dependencies=[Depends(verify_internal_token)])
async def run_signal_validation(req: WorkflowRunRequest) -> Dict[str, Any]:
    workflow = SignalValidationWorkflow()
    out = await workflow.arun(req.payload)
    return {"ok": True, "workflow": "signal_validation", "result": _try_parse_json(out), "ts": int(time.time() * 1000)}


@router.post("/workflow/trade_event", dependencies=[Depends(verify_internal_token)])
async def run_trade_event(req: WorkflowRunRequest) -> Dict[str, Any]:
    workflow = TradeEventWorkflow()
    out = await workflow.arun(req.payload)
    return {"ok": True, "workflow": "trade_event", "result": _try_parse_json(out), "ts": int(time.time() * 1000)}

