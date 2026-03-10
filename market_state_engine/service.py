from __future__ import annotations

import datetime
import logging
import os
import time
from typing import Any, Dict, List, Optional

from market_state_engine.engine import MarketStateEngine
from market_state_engine.errors import FeatureDataUnavailableFromUpstreamError
from market_state_engine.ports.raw_structure_provider import RawStructureProvider
from market_state_engine.ports.selected_event_provider import SelectedEventProvider


_EXTERNAL_EVENT_INPUT_KEYS = {
    "news",
    "social",
    "onchain",
    "sentiment",
    "external_events",
    "active_events",
    "event_stream",
}
_EXTERNAL_INPUT_IGNORED_FLAG = "external_event_input_ignored"
_SELECTED_EVENTS_ATTACHED_FLAG = "selected_event_context_attached"
_SELECTED_EVENTS_UNAVAILABLE_FLAG = "selected_events_unavailable"
_SELECTED_EVENTS_UNVERSIONED_FLAG = "selected_events_unversioned"
_ALERT_CODE_SELECTED_UNVERSIONED = "MSE_SELECTED_EVENTS_UNVERSIONED"

logger = logging.getLogger("market_state_engine")


def _sanitize_market_structure_input(raw_market_structure: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    """仅保留结构状态层输入；忽略外部事件域字段。"""
    cleaned = dict(raw_market_structure or {})
    dropped_keys: list[str] = []
    for key in list(cleaned.keys()):
        key_normalized = str(key or "").strip().lower()
        if key_normalized in _EXTERNAL_EVENT_INPUT_KEYS:
            dropped_keys.append(str(key))
            cleaned.pop(key, None)
    return cleaned, sorted(set([k for k in dropped_keys if k]))


class MarketStateService:
    """状态层用例服务：聚合 raw structure 并产出状态快照。"""

    def __init__(
        self,
        raw_structure_provider: RawStructureProvider,
        selected_event_provider: Optional[SelectedEventProvider] = None,
    ) -> None:
        self._raw_structure_provider = raw_structure_provider
        self._selected_event_provider = selected_event_provider
        self._engine = MarketStateEngine(state_inference_config=self._load_state_inference_config())

    @staticmethod
    def _load_state_inference_config() -> Dict[str, Any]:
        """从环境变量读取插件启停配置。

        - MSE_STATE_PLUGIN_PROFILE=default|fast_mode|risk_only
        - MSE_STATE_PLUGIN_PROFILES_FILE=/abs/path/state_inference_profiles.json
        - MSE_MSL_INFERENCE_VERSION=msl_generator_v1|msl_generator_v2
        - MSE_STATE_PLUGINS_ENABLED=regime_inference,positioning_inference
        - MSE_STATE_PLUGINS_DISABLED=structure_inference
        """
        def _parse_csv(v: str) -> list[str]:
            return [x.strip() for x in str(v or "").split(",") if x.strip()]

        profile = str(os.getenv("MSE_STATE_PLUGIN_PROFILE", "default") or "default").strip() or "default"
        profiles_file = str(os.getenv("MSE_STATE_PLUGIN_PROFILES_FILE", "") or "").strip()
        inference_version = str(os.getenv("MSE_MSL_INFERENCE_VERSION", "msl_generator_v1") or "msl_generator_v1").strip() or "msl_generator_v1"
        enabled = _parse_csv(os.getenv("MSE_STATE_PLUGINS_ENABLED", ""))
        disabled = _parse_csv(os.getenv("MSE_STATE_PLUGINS_DISABLED", ""))
        return {
            "plugin_profile": profile,
            "profiles_file": profiles_file,
            "inference_version": inference_version,
            "enabled_plugins": enabled,
            "disabled_plugins": disabled,
        }

    @staticmethod
    def _build_data_unavailable_payload(exchange: str, symbol: str, degraded_reasons: list[str]) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        ts_iso = (
            datetime.datetime.fromtimestamp(float(now_ms) / 1000.0, tz=datetime.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        return {
            "exchange": exchange,
            "symbol": symbol,
            "status": "data_unavailable",
            "reason_code": "feature_data_unavailable",
            "degraded_reasons": [str(x) for x in list(degraded_reasons or []) if x],
            "msl": {
                "version": 1,
                "timestamp": ts_iso,
                "symbol": symbol,
                "market_regime": {
                    "trend": "unknown",
                    "phase": "unknown",
                    "timeframe_alignment": "unknown",
                    "strength": 0.0,
                },
                "liquidity_state": {
                    "dominant_pressure": "unknown",
                    "liquidity_risk": "unknown",
                    "orderbook_bias": "unknown",
                    "liquidation_proximity": "unknown",
                },
                "positioning_state": {
                    "crowding": "unknown",
                    "whale_bias": "unknown",
                    "retail_bias": "unknown",
                    "oi_trend": "unknown",
                },
                "volatility_state": {
                    "volatility_regime": "unknown",
                    "expansion_risk": "unknown",
                    "volatility_direction": "unknown",
                },
                "risk_state": {
                    "cascade_risk": "unknown",
                    "squeeze_probability": "unknown",
                    "reversal_risk": "unknown",
                },
                "market_structure_state": {
                    "support_strength": "unknown",
                    "resistance_strength": "unknown",
                    "range_state": "unknown",
                    "trend_structure": "unknown",
                },
                "key_levels": {"major_support": [], "major_resistance": [], "liquidation_clusters": []},
                "anomalies": ["data_unavailable"],
                "summary": "上游 feature_service 关键结构数据不可用，状态推断已短路",
            },
            "state_features": {
                "exchange": exchange,
                "symbol": symbol,
                "ts": now_ms,
                "status": "data_unavailable",
                "horizons": {},
                "orderbook": {},
                "open_interest": {},
                "anomalies": {"flags": ["data_unavailable"]},
                "evidence": {"message": "上游 feature_service 关键结构数据不可用"},
                "derived": {},
            },
            "anomaly_flags": ["data_unavailable"],
            "msl_meta": {
                "schema_version": 1,
                "inference_version": "short_circuit_unavailable",
                "inference_profile": "n/a",
            },
            "msl_bundle": {},
            "msl_bundle_meta": {},
            "cross_horizon": {
                "alignment": "unknown",
                "conflicts": [],
                "suggested_policy": "no_action",
                "policy_reason": "insufficient_evidence",
            },
            "raw_market_structure": {},
        }

    async def _collect_selected_events(self, exchange: str, symbol: str) -> tuple[List[Dict[str, Any]], Optional[str]]:
        if self._selected_event_provider is None:
            return [], None
        try:
            selected_events = await self._selected_event_provider.get_selected_events(exchange=exchange, symbol=symbol, limit=20)
            selected_events = [x for x in list(selected_events or []) if isinstance(x, dict)]
            return selected_events, None
        except Exception as exc:
            logger.warning("selected_event_provider 读取失败，已降级忽略: %s", exc)
            return [], _SELECTED_EVENTS_UNAVAILABLE_FLAG

    @staticmethod
    def _build_selected_event_evidence(selected_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        event_types = sorted(
            set([str(x.get("selected_type") or "").strip() for x in selected_events if str(x.get("selected_type") or "").strip()])
        )
        priorities = sorted(
            set([str(x.get("priority") or "").strip() for x in selected_events if str(x.get("priority") or "").strip()])
        )
        directions = sorted(
            set([str(x.get("direction_hint") or "").strip() for x in selected_events if str(x.get("direction_hint") or "").strip()])
        )
        assets = sorted(set([str(x.get("asset") or "").strip() for x in selected_events if str(x.get("asset") or "").strip()]))
        sources = sorted(
            set(
                [
                    str((x.get("source") or {}).get("name") or x.get("source") or "").strip()
                    for x in selected_events
                    if str((x.get("source") or {}).get("name") or x.get("source") or "").strip()
                ]
            )
        )
        schema_versions = sorted(
            set(
                [
                    str((x.get("trace") or {}).get("schema_version") or "").strip()
                    for x in selected_events
                    if str((x.get("trace") or {}).get("schema_version") or "").strip()
                ]
            )
        )
        unversioned_count = 0
        for item in selected_events:
            trace_obj = item.get("trace")
            schema_version = (trace_obj or {}).get("schema_version") if isinstance(trace_obj, dict) else None
            if not isinstance(schema_version, str) or (not schema_version.strip()):
                unversioned_count += 1
        return {
            "selected_events_count": int(len(selected_events)),
            "selected_event_types": event_types,
            "selected_event_priorities": priorities,
            "selected_event_directions": directions,
            "selected_event_assets": assets,
            "selected_event_sources": sources,
            "selected_event_schema_versions": schema_versions,
            "selected_events_unversioned_count": int(unversioned_count),
            "selected_events_preview": selected_events[:3],
        }

    async def get_market_state(self, exchange: str, symbol: str) -> Dict[str, Any]:
        try:
            raw_market_structure = await self._raw_structure_provider.get_raw_structure(exchange=exchange, symbol=symbol)
        except FeatureDataUnavailableFromUpstreamError as exc:
            return self._build_data_unavailable_payload(
                exchange=exc.exchange,
                symbol=exc.symbol,
                degraded_reasons=exc.degraded_reasons,
            )
        if not isinstance(raw_market_structure, dict):
            raise TypeError("invalid_market_structure")

        sanitized_market_structure, dropped_external_keys = _sanitize_market_structure_input(raw_market_structure)
        selected_events, selected_events_error_flag = await self._collect_selected_events(exchange=exchange, symbol=symbol)
        msl, features = self._engine.build(exchange=exchange, symbol=symbol, market_structure=sanitized_market_structure)
        msl_payload = msl.to_llm_dict()
        state_features_payload = features.to_dict()
        anomaly_flags = [str(x) for x in list(features.anomalies.get("flags") or []) if x]
        msl_meta = {}
        if hasattr(self._engine, "get_last_msl_meta"):
            try:
                msl_meta = dict(self._engine.get_last_msl_meta() or {})
            except Exception:
                msl_meta = {}
        msl_bundle: Dict[str, Any] = {}
        msl_bundle_meta: Dict[str, Any] = {}
        cross_horizon: Dict[str, Any] = {
            "alignment": "unknown",
            "conflicts": [],
            "suggested_policy": "no_action",
            "policy_reason": "insufficient_evidence",
        }
        if hasattr(self._engine, "infer_multi_horizon_msl"):
            try:
                msl_bundle, msl_bundle_meta, cross_horizon = self._engine.infer_multi_horizon_msl(features=features)
            except Exception:
                msl_bundle, msl_bundle_meta = {}, {}
                cross_horizon = {
                    "alignment": "unknown",
                    "conflicts": [],
                    "suggested_policy": "no_action",
                    "policy_reason": "insufficient_evidence",
                }

        if selected_events:
            anomaly_flags = sorted(set([*anomaly_flags, _SELECTED_EVENTS_ATTACHED_FLAG]))
            sf_evidence = state_features_payload.get("evidence")
            if not isinstance(sf_evidence, dict):
                sf_evidence = {}
            selected_evidence = self._build_selected_event_evidence(selected_events)
            sf_evidence.update(selected_evidence)
            if int(selected_evidence.get("selected_events_unversioned_count") or 0) > 0:
                anomaly_flags = sorted(set([*anomaly_flags, _SELECTED_EVENTS_UNVERSIONED_FLAG]))
                logger.warning(
                    "告警 code=%s exchange=%s symbol=%s unversioned_count=%s",
                    _ALERT_CODE_SELECTED_UNVERSIONED,
                    exchange,
                    symbol,
                    int(selected_evidence.get("selected_events_unversioned_count") or 0),
                )
            state_features_payload["evidence"] = sf_evidence
        elif selected_events_error_flag:
            anomaly_flags = sorted(set([*anomaly_flags, selected_events_error_flag]))
            sf_evidence = state_features_payload.get("evidence")
            if not isinstance(sf_evidence, dict):
                sf_evidence = {}
            sf_evidence["selected_events_unavailable"] = True
            state_features_payload["evidence"] = sf_evidence

        if dropped_external_keys:
            anomaly_flags = sorted(set([*anomaly_flags, _EXTERNAL_INPUT_IGNORED_FLAG]))

            msl_anomalies = [str(x) for x in list(msl_payload.get("anomalies") or []) if x]
            msl_payload["anomalies"] = sorted(set([*msl_anomalies, _EXTERNAL_INPUT_IGNORED_FLAG]))

            sf_anomalies = state_features_payload.get("anomalies")
            if not isinstance(sf_anomalies, dict):
                sf_anomalies = {}
            sf_flags = [str(x) for x in list(sf_anomalies.get("flags") or []) if x]
            sf_anomalies["flags"] = sorted(set([*sf_flags, _EXTERNAL_INPUT_IGNORED_FLAG]))
            state_features_payload["anomalies"] = sf_anomalies

            sf_evidence = state_features_payload.get("evidence")
            if not isinstance(sf_evidence, dict):
                sf_evidence = {}
            sf_evidence["ignored_external_input_keys"] = list(dropped_external_keys)
            state_features_payload["evidence"] = sf_evidence

        return {
            "exchange": exchange,
            "symbol": symbol,
            "status": "ok",
            "msl": msl_payload,
            "state_features": state_features_payload,
            "anomaly_flags": anomaly_flags,
            "msl_meta": msl_meta,
            "msl_bundle": msl_bundle,
            "msl_bundle_meta": msl_bundle_meta,
            "cross_horizon": cross_horizon,
            "raw_market_structure": sanitized_market_structure,
        }
