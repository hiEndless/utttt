from __future__ import annotations

import logging
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
_SEMANTIC_CONFIDENCE_CANONICAL = "horizons.{hz}.confidence"
_SEMANTIC_CONFIDENCE_ALIAS = "horizons.{hz}.horizon_confidence"
_SEMANTIC_MARKET_STATE_SCOPE = {
    "state_features": "intermediate_features_for_audit_and_debug",
    "msl": "final_fused_state_for_agent_consumption",
}
_SEMANTIC_RISK_SCOPE = {"orderbook", "open_interest"}
logger = logging.getLogger(__name__)


def _normalize_state_features_for_agent(state_features: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    """消费侧收敛歧义别名，保证 agent 内部优先使用 canonical 字段。"""
    out = dict(state_features or {})
    warnings: list[str] = []

    if "market_state" in out and "source_market_state" not in out:
        out["source_market_state"] = out.get("market_state")
        warnings.append("state_features_market_state_alias_applied")
    if "risk_bias" in out and "action_risk_bias" not in out:
        out["action_risk_bias"] = out.get("risk_bias")
        warnings.append("state_features_risk_bias_alias_applied")

    horizons_raw = dict(out.get("horizons") or {})
    horizons_out: Dict[str, Any] = {}
    confidence_alias_applied = False
    for hz in ("short_term", "mid_term", "long_term"):
        node = dict(horizons_raw.get(hz) or {})
        if not node:
            continue
        if ("confidence" not in node) and ("horizon_confidence" in node):
            node["confidence"] = node.get("horizon_confidence")
            confidence_alias_applied = True
        horizons_out[hz] = node
    if horizons_out:
        out["horizons"] = horizons_out
    if confidence_alias_applied:
        warnings.append("state_features_confidence_alias_applied")

    return out, sorted(set([x for x in warnings if x]))

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


def _collect_state_feature_semantic_anomalies(*, data: Dict[str, Any]) -> list[str]:
    anomalies: list[str] = []
    state_features = dict(data.get("state_features") or {})
    semantic_contract = dict(state_features.get("semantic_contract") or {})

    if not semantic_contract:
        anomalies.append("state_features_semantic_contract_missing")
        return anomalies

    confidence_contract = dict(semantic_contract.get("horizon_confidence") or {})
    if str(confidence_contract.get("canonical_field") or "") != _SEMANTIC_CONFIDENCE_CANONICAL:
        anomalies.append("state_features_confidence_canonical_mismatch")
    if str(confidence_contract.get("compat_alias") or "") != _SEMANTIC_CONFIDENCE_ALIAS:
        anomalies.append("state_features_confidence_alias_mismatch")

    horizons = dict(state_features.get("horizons") or {})
    for hz in ("short_term", "mid_term", "long_term"):
        node = dict(horizons.get(hz) or {})
        if not node:
            continue
        c = node.get("confidence")
        hc = node.get("horizon_confidence")
        try:
            c_v = float(c)
            hc_v = float(hc)
        except Exception:
            anomalies.append("state_features_confidence_non_numeric")
            continue
        if c_v != hc_v:
            anomalies.append("state_features_confidence_alias_value_mismatch")
        if c_v < 0.0 or c_v > 1.0:
            anomalies.append("state_features_confidence_out_of_range")

    risk_contract = dict(semantic_contract.get("risk_flags") or {})
    if str(risk_contract.get("canonical_semantics") or "") != "categorical_flags":
        anomalies.append("state_features_risk_flags_semantics_mismatch")
    if str(risk_contract.get("detail_field") or "") != "risk_metrics":
        anomalies.append("state_features_risk_metrics_alias_mismatch")
    risk_scope = {str(x) for x in list(risk_contract.get("scope") or []) if str(x).strip()}
    if risk_scope != _SEMANTIC_RISK_SCOPE:
        anomalies.append("state_features_risk_scope_mismatch")

    for scope in ("orderbook", "open_interest"):
        node = dict(state_features.get(scope) or {})
        if not node:
            continue
        if "risk_flags" in node and not isinstance(node.get("risk_flags"), list):
            anomalies.append("state_features_risk_flags_not_array")
        if scope == "orderbook" and "risk_metrics" in node and not isinstance(node.get("risk_metrics"), dict):
            anomalies.append("state_features_risk_metrics_not_object")

    market_state_vs_msl = dict(semantic_contract.get("market_state_vs_msl") or {})
    if market_state_vs_msl != _SEMANTIC_MARKET_STATE_SCOPE:
        anomalies.append("state_features_market_state_semantics_mismatch")
    if "market_state" in state_features:
        anomalies.append("state_features_market_state_field_ambiguous")
    if "risk_bias" in state_features:
        anomalies.append("state_features_risk_bias_field_ambiguous")

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
        state_features_raw = dict(data.get("state_features") or {})
        state_features, normalization_warnings = _normalize_state_features_for_agent(state_features_raw)
        anomaly_flags = [str(x) for x in list(data.get("anomaly_flags") or []) if x]
        anomaly_flags.extend(_collect_msl_contract_anomalies(data=data))
        anomaly_flags.extend(_collect_state_feature_semantic_anomalies(data=data))
        anomaly_flags.extend(normalization_warnings)
        semantic_anomalies = sorted(set([x for x in anomaly_flags if x.startswith("state_features_")]))
        if semantic_anomalies:
            logger.warning(
                "market_state semantic anomalies exchange=%s symbol=%s flags=%s",
                str(data.get("exchange") or exchange),
                str(data.get("symbol") or symbol),
                ",".join(semantic_anomalies),
            )

        return MarketStateSnapshot(
            exchange=str(data.get("exchange") or exchange),
            symbol=str(data.get("symbol") or symbol),
            msl=_build_msl_from_dict(dict(data.get("msl") or {})),
            msl_meta=dict(data.get("msl_meta") or {}),
            msl_bundle=dict(data.get("msl_bundle") or {}),
            msl_bundle_meta=dict(data.get("msl_bundle_meta") or {}),
            cross_horizon=dict(data.get("cross_horizon") or {}),
            state_features=state_features,
            anomaly_flags=sorted(set([x for x in anomaly_flags if x])),
            raw_market_structure=dict(data.get("raw_market_structure") or {}),
        )
