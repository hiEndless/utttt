from __future__ import annotations

import hashlib
import hmac
import logging
import time
import uuid
from urllib.parse import urlencode
from dataclasses import dataclass
from typing import Any, Dict, Mapping

import aiohttp

from services.execution_service.domain.contracts import DecisionIntent
from services.execution_service.domain.reconcile_statuses import (
    RECONCILE_STATUS_CANCELED,
    RECONCILE_STATUS_FILLED,
    RECONCILE_STATUS_REJECTED,
    RECONCILE_STATUS_SUBMITTED,
)

logger = logging.getLogger(__name__)


@dataclass
class ExchangeExecutionSink:
    """交易所执行适配器（支持 dry-run，便于先联调后实盘）。"""

    venue: str = "binance"
    dry_run: bool = True
    api_base_url: str = "https://api.binance.com"
    api_key: str = ""
    api_secret: str = ""
    recv_window_ms: int = 5000
    default_order_qty: float = 0.001
    timeout_s: float = 5.0

    async def submit(self, decision: DecisionIntent, execution_action: str) -> Dict[str, Any]:
        request_payload = self._build_submit_payload(decision, execution_action)
        order_id = f"{self.venue}-ord-{uuid.uuid4().hex[:12]}"
        if self.dry_run:
            logger.info("交易所下单 dry-run，venue=%s symbol=%s action=%s", self.venue, decision.symbol, execution_action)
            # 中文注释：dry-run 不触发真实下单，返回可追踪请求快照用于联调核对。
            return {
                "submitted": True,
                "mode": "exchange_skeleton",
                "dry_run": True,
                "venue": self.venue,
                "order_id": order_id,
                "decision_id": decision.decision_id,
                "exchange": decision.exchange,
                "account_id": decision.account_id,
                "symbol": decision.symbol.upper(),
                "execution_action": execution_action,
                "status": RECONCILE_STATUS_SUBMITTED,
                "request": request_payload,
                "ts": int(time.time() * 1000),
            }
        if self.venue.lower() != "binance":
            raise RuntimeError(f"exchange venue 暂不支持: {self.venue}")
        out = await self._binance_submit(request_payload)
        return {
            "mode": "exchange_skeleton",
            "dry_run": False,
            "venue": self.venue,
            "submitted": True,
            "order_id": str(out.get("orderId") or order_id),
            "decision_id": decision.decision_id,
            "exchange": decision.exchange,
            "account_id": decision.account_id,
            "symbol": decision.symbol.upper(),
            "execution_action": execution_action,
            "status": RECONCILE_STATUS_SUBMITTED,
            "request": request_payload,
            "exchange_raw": out,
            "ts": int(time.time() * 1000),
        }

    async def reconcile(self, order_id: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        decision_id = str(payload.get("decision_id") or "").strip()
        exchange = str(payload.get("exchange") or "").strip()
        account_id = str(payload.get("account_id") or "").strip()
        symbol = str(payload.get("symbol") or "").strip().upper()
        if self.dry_run:
            # 中文注释：dry-run 对账返回占位状态，避免引入真实交易所依赖。
            return {
                "mode": "exchange_skeleton",
                "dry_run": True,
                "venue": self.venue,
                "order_id": str(order_id),
                "decision_id": decision_id or None,
                "account_id": account_id or None,
                "exchange": exchange or None,
                "symbol": symbol or None,
                "status": RECONCILE_STATUS_SUBMITTED,
                "filled_qty": 0.0,
                "avg_price": None,
                "ts": int(time.time() * 1000),
                "note": "dry-run 占位回执：未请求真实交易所",
            }
        if self.venue.lower() != "binance":
            raise RuntimeError(f"exchange venue 暂不支持: {self.venue}")
        if not symbol:
            raise ValueError("reconcile 需要 symbol")
        out = await self._binance_query_order(symbol=symbol, order_id=str(order_id))
        exchange_status_raw = str(out.get("status") or "").strip().upper()
        reconcile_status = self._map_binance_status(exchange_status_raw)
        executed_qty = _to_float(out.get("executedQty"))
        avg_price = self._compute_avg_price(out=out, executed_qty=executed_qty)
        return {
            "mode": "exchange_skeleton",
            "dry_run": False,
            "venue": self.venue,
            "order_id": str(order_id),
            "decision_id": decision_id or None,
            "account_id": account_id or None,
            "exchange": exchange or None,
            "symbol": symbol or None,
            "status": reconcile_status,
            "filled_qty": executed_qty,
            "avg_price": avg_price,
            "ts": int(time.time() * 1000),
            "exchange_status_raw": exchange_status_raw or None,
            "note": f"交易所回执状态映射: {exchange_status_raw or 'UNKNOWN'} -> {reconcile_status}",
            "exchange_raw": out,
        }

    def _build_submit_payload(self, decision: DecisionIntent, execution_action: str) -> Dict[str, Any]:
        symbol = str(decision.symbol or "").strip().upper()
        if not symbol:
            raise ValueError("symbol 不能为空")
        side = self._derive_order_side(decision=decision, execution_action=execution_action)
        qty = self._extract_order_qty(decision.risk_hints)
        return {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": f"{qty:.6f}",
            "newClientOrderId": f"exec-{decision.decision_id[:20]}-{uuid.uuid4().hex[:6]}",
        }

    def _derive_order_side(self, *, decision: DecisionIntent, execution_action: str) -> str:
        action = str(execution_action or "").strip().lower()
        direction = str(decision.direction_intent or "").strip().lower()
        position_side = str(decision.risk_hints.get("position_side") or "").strip().lower()
        if action == "add":
            if direction == "long":
                return "BUY"
            if direction == "short":
                return "SELL"
            raise ValueError("add 动作必须提供 long/short direction_intent")
        if action in {"reduce", "exit"}:
            # 中文注释：优先使用仓位方向推断平仓方向，避免仅靠意图方向导致反向下单。
            if position_side == "long":
                return "SELL"
            if position_side == "short":
                return "BUY"
            if direction == "long":
                return "SELL"
            if direction == "short":
                return "BUY"
            raise ValueError("reduce/exit 动作需要 position_side 或 long/short direction_intent")
        raise ValueError(f"execution_action 不支持下单: {execution_action}")

    def _extract_order_qty(self, risk_hints: Mapping[str, Any]) -> float:
        raw = (
            risk_hints.get("order_qty")
            if isinstance(risk_hints, Mapping)
            else None
        )
        if raw is None and isinstance(risk_hints, Mapping):
            raw = risk_hints.get("order_quantity")
        if raw is None and isinstance(risk_hints, Mapping):
            raw = risk_hints.get("qty")
        qty = float(raw) if raw is not None else float(self.default_order_qty)
        if qty <= 0:
            raise ValueError("order_qty 必须大于 0")
        return qty

    async def _binance_submit(self, request_payload: Mapping[str, Any]) -> Dict[str, Any]:
        params = dict(request_payload or {})
        params["recvWindow"] = int(self.recv_window_ms)
        params["timestamp"] = int(time.time() * 1000)
        signed = self._sign_params(params)
        return await self._request_binance("POST", "/api/v3/order", signed)

    async def _binance_query_order(self, *, symbol: str, order_id: str) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "symbol": symbol,
            "recvWindow": int(self.recv_window_ms),
            "timestamp": int(time.time() * 1000),
        }
        if str(order_id).strip().isdigit():
            params["orderId"] = str(order_id).strip()
        else:
            params["origClientOrderId"] = str(order_id).strip()
        signed = self._sign_params(params)
        return await self._request_binance("GET", "/api/v3/order", signed)

    def _sign_params(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        if not self.api_key or not self.api_secret:
            raise RuntimeError("binance api_key/api_secret 未配置")
        payload = {k: v for k, v in dict(params).items() if v is not None}
        query = urlencode(payload)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        payload["signature"] = signature
        return payload

    async def _request_binance(self, method: str, path: str, params: Mapping[str, Any]) -> Dict[str, Any]:
        url = f"{self.api_base_url.rstrip('/')}{path}"
        headers = {"X-MBX-APIKEY": self.api_key}
        timeout = aiohttp.ClientTimeout(total=float(self.timeout_s))
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method.upper(), url, params=dict(params or {}), headers=headers) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        raise RuntimeError(f"binance_http_{resp.status}:{text}")
                    data = await resp.json()
                    if not isinstance(data, dict):
                        raise RuntimeError("binance_response_not_object")
                    return dict(data)
        except aiohttp.ClientError as exc:
            logger.warning("交易所请求网络异常 method=%s path=%s err=%s", method, path, exc)
            raise RuntimeError(f"binance_network_error:{exc}") from exc

    def _map_binance_status(self, raw_status: str) -> str:
        status = str(raw_status or "").strip().upper()
        if status in {"FILLED"}:
            return RECONCILE_STATUS_FILLED
        if status in {"CANCELED", "CANCELLED", "EXPIRED", "EXPIRED_IN_MATCH"}:
            return RECONCILE_STATUS_CANCELED
        if status in {"REJECTED"}:
            return RECONCILE_STATUS_REJECTED
        # 中文注释：未识别状态统一回退 submitted，避免误判终态。
        return RECONCILE_STATUS_SUBMITTED

    def _compute_avg_price(self, *, out: Mapping[str, Any], executed_qty: float) -> float | None:
        # 中文注释：优先使用交易所明确返回的 avgPrice；若为空则尝试 quoteQty / executedQty 推导。
        avg_price = _to_float(out.get("avgPrice"))
        if avg_price > 0:
            return avg_price
        if executed_qty > 0:
            quote_qty = _to_float(out.get("cummulativeQuoteQty"))
            if quote_qty > 0:
                return quote_qty / executed_qty
        price = _to_float(out.get("price"))
        if price > 0:
            return price
        return None


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
