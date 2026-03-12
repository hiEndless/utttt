from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

from services.agent_server_new.ports.data.position_context_provider import PositionContextProvider

logger = logging.getLogger(__name__)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _to_bool_env(name: str, default: str) -> bool:
    return str(os.getenv(name, default) or default).strip().lower() in {"1", "true", "yes", "on"}


class HttpExecutionPositionContextProvider(PositionContextProvider):
    """通过 execution_service debug state 读取仓位/账户上下文。"""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 10.0,
        account_id: str = "main",
        redact: bool = True,
        fail_open: bool = True,
    ) -> None:
        self._base_url = str(base_url or "").rstrip("/")
        self._timeout_s = float(timeout_s)
        self._account_id = str(account_id or "main").strip() or "main"
        self._redact = bool(redact)
        self._fail_open = bool(fail_open)

    @classmethod
    def from_env(cls, *, runtime_profile: str | None = None) -> "HttpExecutionPositionContextProvider":
        profile = str(runtime_profile or os.getenv("AGENT_RUNTIME_PROFILE", "dev") or "dev").strip().lower()
        default_base_url = str(
            os.getenv("AGENT_EXECUTION_BASE_URL", "http://127.0.0.1:9962") or "http://127.0.0.1:9962"
        ).strip()
        base_url = str(os.getenv("AGENT_POSITION_CONTEXT_BASE_URL", default_base_url) or default_base_url).strip()
        timeout_raw = str(
            os.getenv("AGENT_POSITION_CONTEXT_TIMEOUT_S", os.getenv("AGENT_EXECUTION_TIMEOUT_S", "10") or "10")
            or "10"
        ).strip()
        try:
            timeout_s = float(timeout_raw)
        except Exception:
            timeout_s = 10.0
        account_id = str(os.getenv("AGENT_POSITION_CONTEXT_ACCOUNT_ID", "main") or "main").strip() or "main"
        redact = _to_bool_env("AGENT_POSITION_CONTEXT_REDACT", "true")
        # 中文注释：prod 默认 fail-closed；dev 默认 fail-open，避免阻塞本地联调。
        fail_open_default = "false" if profile in {"prod", "production"} else "true"
        fail_open = _to_bool_env("AGENT_POSITION_CONTEXT_FAIL_OPEN", fail_open_default)
        return cls(
            base_url=base_url,
            timeout_s=timeout_s,
            account_id=account_id,
            redact=redact,
            fail_open=fail_open,
        )

    async def get_position_context(self, exchange: str, symbol: str) -> Dict[str, Any]:
        url = f"{self._base_url}/internal/execution/debug/state/{exchange}/{symbol}"
        params = {"redact": "true" if self._redact else "false", "account_id": self._account_id}
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = dict(response.json() or {})
        except Exception as exc:
            if not self._fail_open:
                raise
            logger.warning("position_context http provider failed, fallback empty context: %s", exc)
            return {
                "exchange": exchange,
                "symbol": symbol,
                "account_id": self._account_id,
                "has_position": False,
                "current_position": None,
                "avg_entry": None,
                "exposure": None,
                "margin": None,
                "portfolio_risk": None,
                "source": "execution_service_debug_state_fallback",
            }

        position_state = dict(payload.get("position_state") or {})
        account_state = dict(payload.get("account_state") or {})
        position_side = str(position_state.get("position_side") or "flat").strip().lower()
        position_size = _to_float(position_state.get("position_size"), 0.0)
        long_position_size = _to_float(position_state.get("long_position_size"), 0.0)
        short_position_size = _to_float(position_state.get("short_position_size"), 0.0)
        has_position = abs(position_size) > 0 or position_side in {"long", "short"}
        max_position_size = _to_float(position_state.get("max_position_size"), 0.0)

        return {
            "exchange": str(payload.get("exchange") or exchange),
            "symbol": str(payload.get("symbol") or symbol),
            "account_id": str(payload.get("account_id") or self._account_id),
            "has_position": bool(has_position),
            "current_position": {
                "position_side": position_side,
                "position_size": position_size,
                "long_position_size": long_position_size,
                "short_position_size": short_position_size,
                "unrealized_pnl": _to_float(position_state.get("unrealized_pnl"), 0.0),
                "cooldown_seconds_left": int(position_state.get("cooldown_seconds_left") or 0),
            },
            "avg_entry": position_state.get("avg_entry_price"),
            "exposure": {
                "position_size": position_size,
                "max_position_size": max_position_size,
                "ratio": (position_size / max_position_size) if max_position_size > 0 else None,
            },
            "margin": {
                "margin_ratio": _to_float(account_state.get("margin_ratio"), 0.0),
                "available_balance": account_state.get("available_balance"),
                "account_equity": account_state.get("account_equity"),
            },
            "portfolio_risk": {
                "risk_state": str(account_state.get("risk_state") or "normal"),
                "current_drawdown_ratio": _to_float(account_state.get("current_drawdown_ratio"), 0.0),
                "daily_loss": _to_float(account_state.get("daily_loss"), 0.0),
                "consecutive_loss_count": int(account_state.get("consecutive_loss_count") or 0),
            },
            "source": "execution_service_debug_state",
        }

