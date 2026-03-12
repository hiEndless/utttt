from __future__ import annotations

import datetime
import logging
import os
import time
from typing import Any, Dict, List, Optional

from contracts.semantic_policies.source_semantics import (
    get_alternative_source_allowed_provider_states,
    get_alternative_source_unavailable_provider_states,
)
from services.market_state_engine.src.engine import MarketStateEngine
from services.market_state_engine.src.errors import FeatureDataUnavailableFromUpstreamError
from services.market_state_engine.src.ports.raw_structure_provider import RawStructureProvider
from services.market_state_engine.src.ports.selected_event_provider import SelectedEventProvider


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
_ALTERNATIVE_SOURCE_PROVIDER_STATE_INVALID_FLAG = "state_features_alternative_source_provider_state_invalid"
_ALERT_CODE_SELECTED_UNVERSIONED = "MSE_SELECTED_EVENTS_UNVERSIONED"
_ALTERNATIVE_SOURCE_ALLOWED_PROVIDER_STATES = get_alternative_source_allowed_provider_states()

logger = logging.getLogger("market_state_engine")
_UNAVAILABLE_PROVIDER_STATES = get_alternative_source_unavailable_provider_states()


def _has_nonempty_features(features: Any) -> bool:
    return isinstance(features, dict) and any(v is not None for v in features.values())


def _is_effective_alternative_source_entry(entry: Dict[str, Any]) -> bool:
    provider_state = str(entry.get("provider_state") or "").strip().lower()
    has_features = _has_nonempty_features(entry.get("features"))
    if provider_state in _UNAVAILABLE_PROVIDER_STATES and not has_features:
        return False
    if bool(entry.get("available")):
        return True
    return has_features


def _normalize_alternative_source_entry(source_type: str, payload: Any) -> Dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    features = raw.get("features")
    if not isinstance(features, dict):
        features = {}
    available = bool(raw.get("available")) if "available" in raw else bool(features)
    provider_state = str(raw.get("provider_state") or ("ok" if available else "empty"))
    if str(provider_state).strip().lower() in _UNAVAILABLE_PROVIDER_STATES and not _has_nonempty_features(features):
        available = False
    data_source = str(raw.get("data_source") or raw.get("source") or f"feature_service.{source_type}").strip()
    inference_source = str(raw.get("inference_source") or "feature_service.normalizer").strip()
    return {
        "source_type": source_type,
        "available": available,
        "provider_state": provider_state,
        "data_source": data_source or f"feature_service.{source_type}",
        "inference_source": inference_source or "feature_service.normalizer",
        "as_of_ms": raw.get("as_of_ms"),
        "features": dict(features),
    }


def _extract_alternative_sources(raw_market_structure: Dict[str, Any]) -> Dict[str, Any]:
    alt = raw_market_structure.get("alternative_sources")
    alt_obj = alt if isinstance(alt, dict) else {}
    return {
        "news": _normalize_alternative_source_entry("news", alt_obj.get("news")),
        "social": _normalize_alternative_source_entry("social", alt_obj.get("social")),
        "onchain": _normalize_alternative_source_entry("onchain", alt_obj.get("onchain")),
    }


def _empty_event_alt_summary() -> Dict[str, Any]:
    sources = ("news", "social", "onchain")
    return {
        "available_sources": [],
        "unavailable_sources": list(sources),
        "provider_states": {x: "empty" for x in sources},
        "data_sources": {x: f"event_center_new.{x}" for x in sources},
        "inference_sources": {x: "event_center_new.selector" for x in sources},
        "feature_keys": {x: [] for x in sources},
        "evidence_counts": {x: 0 for x in sources},
    }


def _normalize_event_alt_summary(payload: Any) -> Dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    base = _empty_event_alt_summary()
    available = [str(x) for x in list(raw.get("available_sources") or []) if str(x).strip()]
    unavailable = [str(x) for x in list(raw.get("unavailable_sources") or []) if str(x).strip()]
    provider_states = raw.get("provider_states")
    data_sources = raw.get("data_sources")
    inference_sources = raw.get("inference_sources")
    feature_keys = raw.get("feature_keys")
    evidence_counts = raw.get("evidence_counts")
    if isinstance(provider_states, dict):
        base["provider_states"] = {k: str(v) for k, v in provider_states.items() if str(k).strip()}
    if isinstance(feature_keys, dict):
        base["feature_keys"] = {
            str(k): sorted([str(x) for x in list(v or []) if str(x).strip()])
            for k, v in feature_keys.items()
            if str(k).strip()
        }
    if isinstance(data_sources, dict):
        base["data_sources"] = {str(k): str(v) for k, v in data_sources.items() if str(k).strip() and str(v).strip()}
    if isinstance(inference_sources, dict):
        base["inference_sources"] = {
            str(k): str(v) for k, v in inference_sources.items() if str(k).strip() and str(v).strip()
        }
    if isinstance(evidence_counts, dict):
        out_counts: Dict[str, int] = {}
        for k, v in evidence_counts.items():
            key = str(k).strip()
            if not key:
                continue
            try:
                out_counts[key] = max(0, int(v))
            except Exception:
                out_counts[key] = 0
        base["evidence_counts"] = out_counts
    base["available_sources"] = sorted(set(available))
    base["unavailable_sources"] = sorted(set(unavailable))
    return base


def _collect_event_alt_summary_from_selected_events(selected_events: List[Dict[str, Any]]) -> Dict[str, Any]:
    sources = ("news", "social", "onchain")
    counts: Dict[str, int] = {x: 0 for x in sources}
    provider_states: Dict[str, str] = {x: "empty" for x in sources}
    data_sources: Dict[str, str] = {x: f"event_center_new.{x}" for x in sources}
    inference_sources: Dict[str, str] = {x: "event_center_new.selector" for x in sources}
    feature_keys: Dict[str, set[str]] = {x: set() for x in sources}
    found = False
    for item in selected_events:
        ctx = item.get("context_snapshot")
        summary = _normalize_event_alt_summary((ctx or {}).get("alternative_sources_summary") if isinstance(ctx, dict) else None)
        if summary == _empty_event_alt_summary():
            continue
        found = True
        for src in sources:
            counts[src] += int(dict(summary.get("evidence_counts") or {}).get(src) or 0)
            state = str(dict(summary.get("provider_states") or {}).get(src) or "")
            if state and state != "empty":
                provider_states[src] = state
            data_source = str(dict(summary.get("data_sources") or {}).get(src) or "").strip()
            if data_source:
                data_sources[src] = data_source
            inference_source = str(dict(summary.get("inference_sources") or {}).get(src) or "").strip()
            if inference_source:
                inference_sources[src] = inference_source
            keys = list(dict(summary.get("feature_keys") or {}).get(src) or [])
            for k in keys:
                ks = str(k).strip()
                if ks:
                    feature_keys[src].add(ks)
    if not found:
        return _empty_event_alt_summary()
    available = [x for x in sources if counts[x] > 0]
    unavailable = [x for x in sources if counts[x] <= 0]
    return {
        "available_sources": available,
        "unavailable_sources": unavailable,
        "provider_states": provider_states,
        "data_sources": data_sources,
        "inference_sources": inference_sources,
        "feature_keys": {x: sorted(feature_keys[x]) for x in sources},
        "evidence_counts": counts,
    }


def _build_alternative_sources_fusion(*, feature_alt: Dict[str, Any], event_alt_summary: Dict[str, Any]) -> Dict[str, Any]:
    sources = ("news", "social", "onchain")
    merged: Dict[str, Any] = {}
    conflicts: List[Dict[str, str]] = []
    event_states = dict(event_alt_summary.get("provider_states") or {})
    event_data_sources = dict(event_alt_summary.get("data_sources") or {})
    event_inference_sources = dict(event_alt_summary.get("inference_sources") or {})
    event_keys = dict(event_alt_summary.get("feature_keys") or {})
    event_counts = dict(event_alt_summary.get("evidence_counts") or {})

    for src in sources:
        feat = _normalize_alternative_source_entry(src, feature_alt.get(src))
        feat_available = _is_effective_alternative_source_entry(feat)
        feat_state = str(feat.get("provider_state") or "empty")
        feat_data_source = str(feat.get("data_source") or f"feature_service.{src}")
        feat_inference_source = str(feat.get("inference_source") or "feature_service.normalizer")
        feat_keys = sorted([str(x) for x in dict(feat.get("features") or {}).keys() if str(x).strip()])

        ev_state = str(event_states.get(src) or "empty")
        ev_data_source = str(event_data_sources.get(src) or f"event_center_new.{src}")
        ev_inference_source = str(event_inference_sources.get(src) or "event_center_new.selector")
        ev_keys = sorted([str(x) for x in list(event_keys.get(src) or []) if str(x).strip()])
        ev_count = int(event_counts.get(src) or 0)
        ev_available = ev_count > 0

        available = feat_available or ev_available
        chosen_state = feat_state if feat_available else (ev_state if ev_available else "empty")
        chosen_data_source = feat_data_source if feat_available else (ev_data_source if ev_available else "none")
        chosen_inference_source = (
            feat_inference_source if feat_available else (ev_inference_source if ev_available else "none")
        )
        all_keys = sorted(set([*feat_keys, *ev_keys]))
        if feat_available and ev_available and feat_state != ev_state:
            conflicts.append({"source": src, "feature_state": feat_state, "event_state": ev_state})

        merged[src] = {
            "source_type": src,
            "available": available,
            "provider_state": chosen_state,
            "data_source": chosen_data_source,
            "inference_source": chosen_inference_source,
            "feature_data_source": feat_data_source,
            "event_data_source": ev_data_source,
            "feature_inference_source": feat_inference_source,
            "event_inference_source": ev_inference_source,
            "feature_keys": all_keys,
            "feature_available": feat_available,
            "event_available": ev_available,
            "event_evidence_count": ev_count,
        }

    available_sources = [x for x in sources if merged[x]["available"]]
    unavailable_sources = [x for x in sources if not merged[x]["available"]]
    feature_available = any(_is_effective_alternative_source_entry(_normalize_alternative_source_entry(x, feature_alt.get(x))) for x in sources)
    preferred_source = "feature" if feature_available else ("event_center" if any(int(event_counts.get(x) or 0) > 0 for x in sources) else "none")
    return {
        "preferred_source": preferred_source,
        "conflicts": conflicts,
        "feature": dict(feature_alt),
        "event_center": dict(event_alt_summary),
        "merged": {
            "available_sources": available_sources,
            "unavailable_sources": unavailable_sources,
            "by_source": merged,
        },
    }


def _collect_invalid_provider_states_from_fusion(fusion: Dict[str, Any]) -> list[str]:
    merged = dict((fusion or {}).get("merged") or {})
    by_source = dict(merged.get("by_source") or {})
    invalid: list[str] = []
    for src in ("news", "social", "onchain"):
        node = dict(by_source.get(src) or {})
        state = str(node.get("provider_state") or "").strip().lower()
        if not state:
            continue
        if state not in _ALTERNATIVE_SOURCE_ALLOWED_PROVIDER_STATES:
            invalid.append(src)
    return sorted(set(invalid))


def _sanitize_market_structure_input(raw_market_structure: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    """仅保留结构状态层输入；忽略外部事件域字段。"""
    cleaned = dict(raw_market_structure or {})
    dropped_keys: list[str] = []
    for key in list(cleaned.keys()):
        key_normalized = str(key or "").strip().lower()
        if key_normalized in _EXTERNAL_EVENT_INPUT_KEYS:
            dropped_keys.append(str(key))
            cleaned.pop(key, None)
    cleaned["alternative_sources"] = _extract_alternative_sources(raw_market_structure)
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
                "market_risk_state": {
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
        preview: list[Dict[str, Any]] = []
        for item in selected_events[:3]:
            row = dict(item)
            event_ts = row.get("event_ts_ms")
            processed_ts = row.get("processed_ts_ms")
            if event_ts is None:
                event_ts = row.get("ts_ms")
            if processed_ts is None:
                processed_ts = row.get("ts_ms")
            if event_ts is not None:
                row["event_ts_ms"] = event_ts
            if processed_ts is not None:
                row["processed_ts_ms"] = processed_ts
            preview.append(row)

        return {
            "selected_events_count": int(len(selected_events)),
            "selected_event_types": event_types,
            "selected_event_priorities": priorities,
            "selected_event_directions": directions,
            "selected_event_assets": assets,
            "selected_event_sources": sources,
            "selected_event_schema_versions": schema_versions,
            "selected_events_unversioned_count": int(unversioned_count),
            "selected_events_preview": preview,
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
        # 字段语义锚点：降低跨服务消费时的隐式语义漂移风险。
        state_features_payload["semantic_contract"] = {
            "horizon_confidence": {
                "canonical_field": "horizons.{hz}.confidence",
                "compat_alias": "horizons.{hz}.horizon_confidence",
                "status": "compat_alias",
            },
            "risk_flags": {
                "canonical_semantics": "categorical_flags",
                "detail_field": "risk_metrics",
                "scope": ["orderbook", "open_interest"],
            },
            "market_state_vs_msl": {
                "state_features": "intermediate_features_for_audit_and_debug",
                "msl": "final_fused_state_for_agent_consumption",
            },
        }
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

        sf_evidence = state_features_payload.get("evidence")
        if not isinstance(sf_evidence, dict):
            sf_evidence = {}
        feature_alt = _extract_alternative_sources(sanitized_market_structure)
        event_alt_summary = _collect_event_alt_summary_from_selected_events(selected_events)
        fusion = _build_alternative_sources_fusion(
            feature_alt=feature_alt,
            event_alt_summary=event_alt_summary,
        )
        sf_evidence["alternative_sources_fusion"] = fusion
        invalid_provider_state_sources = _collect_invalid_provider_states_from_fusion(fusion)
        if invalid_provider_state_sources:
            anomaly_flags = sorted(set([*anomaly_flags, _ALTERNATIVE_SOURCE_PROVIDER_STATE_INVALID_FLAG]))
            sf_evidence["alternative_source_provider_state_invalid_sources"] = list(invalid_provider_state_sources)
        state_features_payload["evidence"] = sf_evidence

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
