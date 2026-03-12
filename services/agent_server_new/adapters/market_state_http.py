from __future__ import annotations

import os
from typing import Any, Dict

import httpx

from services.agent_server_new.domain.msl_parser import _build_msl_from_dict
from services.agent_server_new.ports.market_state import MarketStateProvider, MarketStateSnapshot

_MSL_REQUIRED_FIELDS = {
    "version",
    "timestamp",
    "symbol",
    "market_regime",
    "liquidity_state",
    "positioning_state",
    "volatility_state",
    "market_risk_state",
    "market_structure_state",
    "key_levels",
    "anomalies",
    "summary",
}
_MSL_SUPPORTED_SCHEMA_VERSIONS = {1, 2}

def _collect_msl_contract_anomalies(*, data: Dict[str, Any]) -> list[str]:
    anomalies: list[str] = []
    msl_raw = dict(data.get("msl") or {})
    msl_meta = dict(data.get("msl_meta") or {})

    missing = sorted([k for k in _MSL_REQUIRED_FIELDS if k not in msl_raw])
    if "market_risk_state" in missing and "risk_state" in msl_raw:
        missing.remove("market_risk_state")
        anomalies.append("msl_contract_legacy_risk_state_alias")
    if missing:
        anomalies.append("msl_contract_missing_required_fields")

    schema_version_raw = msl_meta.get("schema_version")
    schema_version = None
    try:
        schema_version = int(schema_version_raw)
    except Exception:
        schema_version = None
    if schema_version is None:
        anomalies.append("msl_meta_schema_version_missing")
    elif schema_version not in _MSL_SUPPORTED_SCHEMA_VERSIONS:
        anomalies.append("msl_meta_schema_version_unsupported")
    else:
        try:
            msl_version = int(msl_raw.get("version"))
        except Exception:
            msl_version = None
        if msl_version != schema_version:
            anomalies.append("msl_version_schema_version_mismatch")
    return sorted(set([x for x in anomalies if x]))


class HttpMarketStateProvider(MarketStateProvider):
    """通过 HTTP 访问独立的 market_state_engine 服务。"""

    def __init__(self, base_url: str, *, timeout_s: float = 10.0) -> None:
        self._base_url = str(base_url or "").rstrip("/")
        self._timeout_s = float(timeout_s)

    @classmethod
    def from_env(cls) -> "HttpMarketStateProvider":
        """从环境变量构建 provider。"""
        base_url = str(os.getenv("AGENT_MARKET_STATE_BASE_URL", "http://127.0.0.1:8300") or "http://127.0.0.1:8300").strip()
        timeout_raw = str(os.getenv("AGENT_MARKET_STATE_TIMEOUT_S", "10") or "10").strip()
        try:
            timeout_s = float(timeout_raw)
        except Exception:
            timeout_s = 10.0
        return cls(base_url=base_url, timeout_s=timeout_s)

    async def get_market_state(self, exchange: str, symbol: str) -> MarketStateSnapshot:
        url = f"{self._base_url}/internal/market-state/{exchange}/{symbol}"
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        data = dict(data or {})
        anomaly_flags = [str(x) for x in list(data.get("anomaly_flags") or []) if x]
        anomaly_flags.extend(_collect_msl_contract_anomalies(data=data))

        return MarketStateSnapshot(
            exchange=str(data.get("exchange") or exchange),
            symbol=str(data.get("symbol") or symbol),
            msl=_build_msl_from_dict(dict(data.get("msl") or {})),
            msl_meta=dict(data.get("msl_meta") or {}),
            msl_bundle=dict(data.get("msl_bundle") or {}),
            msl_bundle_meta=dict(data.get("msl_bundle_meta") or {}),
            cross_horizon=dict(data.get("cross_horizon") or {}),
            state_features=dict(data.get("state_features") or {}),
            anomaly_flags=sorted(set([x for x in anomaly_flags if x])),
            raw_market_structure=dict(data.get("raw_market_structure") or {}),
        )
