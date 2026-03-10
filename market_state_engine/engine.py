from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .contracts import MarketStateMSL
from .ports.storage.feature_store import FeatureStore
from .state_inference import infer_msl_with_meta


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _safe_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _safe_text(x: Any) -> str:
    try:
        return str(x or "")
    except Exception:
        return ""


def _normalize_risk_flags(value: Any) -> List[str]:
    if isinstance(value, list):
        return sorted(set([str(x) for x in value if str(x or "").strip()]))
    if isinstance(value, dict):
        out: List[str] = []
        for k, v in value.items():
            name = str(k or "").strip()
            if not name:
                continue
            if isinstance(v, str) and v.strip().lower() in {"0", "false", "no", "off", ""}:
                continue
            if bool(v):
                out.append(name)
        return sorted(set(out))
    return []


@dataclass(frozen=True)
class MarketStateFeatures:

    exchange: str
    symbol: str
    ts: int

    horizons: Dict[str, Any]
    orderbook: Dict[str, Any]
    open_interest: Dict[str, Any]

    anomalies: Dict[str, Any]
    evidence: Dict[str, Any]
    derived: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "ts": self.ts,
            "horizons": dict(self.horizons),
            "orderbook": dict(self.orderbook),
            "open_interest": dict(self.open_interest),
            "anomalies": dict(self.anomalies),
            "evidence": dict(self.evidence),
            "derived": dict(self.derived),
        }


class MarketStateEngine:
    """市场状态引擎：raw_structure -> feature_aggregation -> anomaly_detection -> evidence_extraction -> state_inference -> MSL。"""

    def __init__(
        self,
        *,
        feature_store: Optional[FeatureStore] = None,
        state_inference_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._feature_store = feature_store
        # 可选：按配置启停 state_inference 插件，默认全启用。
        self._state_inference_config = state_inference_config if isinstance(state_inference_config, dict) else None
        self._last_msl_meta: Dict[str, Any] = {}

    def aggregate_features(self, *, exchange: str, symbol: str, market_structure: Dict[str, Any]) -> MarketStateFeatures:
        now_ts = int(time.time() * 1000)

        fused = _safe_dict(_safe_dict(market_structure.get("horizons")).get("fused"))
        hz = _safe_dict(fused.get("horizons"))
        short_hz = _safe_dict(hz.get("short_term"))
        mid_hz = _safe_dict(hz.get("mid_term"))
        long_hz = _safe_dict(hz.get("long_term"))

        pre = _safe_dict(market_structure.get("pre_decision_structure"))
        st = _safe_dict(pre.get("short_term"))
        mt = _safe_dict(pre.get("mid_term"))
        lt = _safe_dict(pre.get("long_term"))

        micro = _safe_dict(st.get("micro_liquidity"))
        ob_meta = _safe_dict(micro.get("meta"))
        ob_risk_flags = _safe_dict(micro.get("risk_flags"))
        st_risks = _safe_dict(st.get("structural_risks"))

        pp = _safe_dict(mt.get("participant_positioning"))
        oi_delta = _safe_dict(pp.get("oi_delta"))
        oi_dyn = _safe_dict(pp.get("oi_dynamics"))
        oi_flags = _normalize_risk_flags(pp.get("risk_flags"))
        ob_flags = _normalize_risk_flags(ob_risk_flags)

        short_mb = _safe_dict(short_hz.get("market_background"))
        mid_mb = _safe_dict(mid_hz.get("market_background"))
        mid_pb = _safe_dict(mid_hz.get("participant_background"))
        long_mb = _safe_dict(long_hz.get("market_background"))

        horizons_out = {
            "short_term": {
                "market_background": {
                    "trend_memory": _safe_dict(short_mb.get("trend_memory")),
                    "trend_context": short_mb.get("trend_context"),
                    "structure_state": short_mb.get("structure_state"),
                    "risk_level": short_mb.get("risk_level"),
                    "volatility_state": short_mb.get("volatility_state"),
                },
                "participant_background": _safe_dict(short_hz.get("participant_background")),
                "confidence": float(short_hz.get("confidence") or 0.0),
                "horizon_confidence": float(short_hz.get("confidence") or 0.0),
            },
            "mid_term": {
                "market_background": {
                    "trend_memory": _safe_dict(mid_mb.get("trend_memory")),
                    "trend_context": mid_mb.get("trend_context"),
                    "structure_state": mid_mb.get("structure_state"),
                    "risk_level": mid_mb.get("risk_level"),
                    "volatility_state": mid_mb.get("volatility_state"),
                },
                "participant_background": mid_pb,
                "confidence": float(mid_hz.get("confidence") or 0.0),
                "horizon_confidence": float(mid_hz.get("confidence") or 0.0),
            },
            "long_term": {
                "market_background": {
                    "trend_memory": _safe_dict(long_mb.get("trend_memory")),
                    "trend_context": long_mb.get("trend_context"),
                    "structure_state": long_mb.get("structure_state"),
                    "risk_level": long_mb.get("risk_level"),
                    "volatility_state": long_mb.get("volatility_state"),
                },
                "participant_background": _safe_dict(long_hz.get("participant_background")),
                "confidence": float(long_hz.get("confidence") or 0.0),
                "horizon_confidence": float(long_hz.get("confidence") or 0.0),
            },
        }

        orderbook_out = {
            "stability": _safe_text(ob_meta.get("stability")),
            "liquidity_vacuum": bool(st_risks.get("liquidity_vacuum") is True or ob_risk_flags.get("liquidity_vacuum_event") is True),
            "risk_flags": list(ob_flags),
            # 明细风险数值/布尔位：保留 map 语义，避免信息丢失。
            "risk_metrics": dict(ob_risk_flags),
        }

        open_interest_out = {
            "delta_oi_pct": float(oi_delta.get("delta_oi_pct") or 0.0),
            "oi_trend": _safe_text(oi_dyn.get("oi_trend")),
            "oi_velocity": _safe_text(oi_dyn.get("oi_velocity")),
            "oi_acceleration": _safe_text(oi_dyn.get("oi_acceleration")),
            "risk_flags": list(oi_flags),
        }

        derived = {
            "pre_decision_short_term_structural_risks": dict(st_risks),
            "pre_decision_mid_term_structural_risks": dict(_safe_dict(mt.get("structural_risks"))),
            "pre_decision_long_term_structural_context": dict(_safe_dict(lt.get("structural_context"))),
        }

        return MarketStateFeatures(
            exchange=exchange,
            symbol=symbol,
            ts=now_ts,
            horizons=horizons_out,
            orderbook=orderbook_out,
            open_interest=open_interest_out,
            anomalies={},
            evidence={},
            derived=derived,
        )

    def detect_anomalies(self, *, features: MarketStateFeatures) -> Dict[str, Any]:
        ob = _safe_dict(features.orderbook)
        oi = _safe_dict(features.open_interest)
        derived = _safe_dict(features.derived)

        anomalies: Dict[str, Any] = {"flags": []}

        if bool(ob.get("liquidity_vacuum") is True):
            anomalies["flags"].append("orderbook_liquidity_vacuum")

        try:
            d_pct = float(oi.get("delta_oi_pct") or 0.0)
        except Exception:
            d_pct = 0.0
        if abs(d_pct) >= 0.03:
            anomalies["flags"].append("oi_spike")
            anomalies["oi_spike"] = {"delta_oi_pct": float(d_pct)}

        oi_flags = [str(x) for x in _safe_list(oi.get("risk_flags")) if x]
        if any(x in {"possible_liquidation_or_unwind", "fragile_leverage_build"} for x in oi_flags):
            anomalies["flags"].append("liquidation_cluster")

        lt_ctx = _safe_dict(derived.get("pre_decision_long_term_structural_context"))
        if bool(lt_ctx.get("leverage_extreme") is True):
            anomalies["flags"].append("leverage_extreme")
        cp = _safe_dict(lt_ctx.get("crowding_percentile"))
        zone = _safe_text(cp.get("zone"))
        if zone in ("elevated", "extreme"):
            anomalies["flags"].append("crowding_extreme")

        anomalies["flags"] = sorted(set([str(x) for x in anomalies["flags"] if x]))
        return anomalies

    def extract_evidence(self, *, features: MarketStateFeatures, anomalies: Dict[str, Any]) -> Dict[str, Any]:
        """提取可解释证据层：面向 LLM 与调试输出，保持字段少且稳定。"""

        mid = _safe_dict(features.horizons.get("mid_term"))
        mid_mb = _safe_dict(mid.get("market_background"))
        mid_tm = _safe_dict(mid_mb.get("trend_memory"))
        mid_pb = _safe_dict(mid.get("participant_background"))

        ob = _safe_dict(features.orderbook)
        oi = _safe_dict(features.open_interest)

        return {
            "price_direction_mid": _safe_text(mid_tm.get("price_direction")),
            "price_strength_mid": _safe_text(mid_tm.get("price_strength")),
            "volatility_state_mid": _safe_text(mid_mb.get("volatility_state")),
            "crowding_mid": _safe_text(mid_pb.get("crowding")),
            "participant_stability_mid": _safe_text(mid_pb.get("stability")),
            "liquidity_vacuum": bool(ob.get("liquidity_vacuum") is True),
            "orderbook_stability": _safe_text(ob.get("stability")),
            "oi_trend": _safe_text(oi.get("oi_trend")),
            "oi_velocity": _safe_text(oi.get("oi_velocity")),
            "oi_acceleration": _safe_text(oi.get("oi_acceleration")),
            "delta_oi_pct": float(oi.get("delta_oi_pct") or 0.0),
            "anomaly_flags": [str(x) for x in _safe_list(_safe_dict(anomalies).get("flags")) if x],
        }

    def infer_msl(self, *, features: MarketStateFeatures) -> MarketStateMSL:
        # MSL 由可插拔 state_inference 流水线生成。
        msl, meta = infer_msl_with_meta(features=features, plugin_config=self._state_inference_config)
        self._last_msl_meta = dict(meta or {})
        return msl

    def get_last_msl_meta(self) -> Dict[str, Any]:
        return dict(self._last_msl_meta or {})

    def _build_features_for_horizon(self, *, features: MarketStateFeatures, horizon: str) -> MarketStateFeatures:
        """将指定周期映射到推断引擎所需的 short/mid 视图。"""
        hz = _safe_dict(features.horizons)
        short_hz = _safe_dict(hz.get("short_term"))
        mid_hz = _safe_dict(hz.get("mid_term"))
        long_hz = _safe_dict(hz.get("long_term"))

        if horizon == "short_term":
            # 短线视图：short 作为主分析对象，mid 使用同一视图避免缺失。
            mapped_horizons = {
                "short_term": dict(short_hz),
                "mid_term": dict(short_hz),
                "long_term": dict(long_hz),
            }
        elif horizon == "long_term":
            # 长线视图：long 作为主分析对象，short 用 mid 作为近端参考。
            mapped_horizons = {
                "short_term": dict(mid_hz),
                "mid_term": dict(long_hz),
                "long_term": dict(long_hz),
            }
        else:
            # 中线视图保持原语义。
            mapped_horizons = {
                "short_term": dict(short_hz),
                "mid_term": dict(mid_hz),
                "long_term": dict(long_hz),
            }

        return MarketStateFeatures(
            exchange=features.exchange,
            symbol=features.symbol,
            ts=features.ts,
            horizons=mapped_horizons,
            orderbook=dict(features.orderbook),
            open_interest=dict(features.open_interest),
            anomalies=dict(features.anomalies),
            evidence=dict(features.evidence),
            derived=dict(features.derived),
        )

    @staticmethod
    def _build_cross_horizon(bundle: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        def _h(hz: str) -> Dict[str, Any]:
            return _safe_dict(bundle.get(hz))

        short = _h("short_term")
        mid = _h("mid_term")
        long = _h("long_term")

        # 冲突规则优先级（高->低）：trend > phase > volatility_regime > liquidity_risk
        fields = [
            ("trend", _safe_text(_safe_dict(short.get("market_regime")).get("trend")), _safe_text(_safe_dict(mid.get("market_regime")).get("trend")), _safe_text(_safe_dict(long.get("market_regime")).get("trend"))),
            ("phase", _safe_text(_safe_dict(short.get("market_regime")).get("phase")), _safe_text(_safe_dict(mid.get("market_regime")).get("phase")), _safe_text(_safe_dict(long.get("market_regime")).get("phase"))),
            (
                "volatility_regime",
                _safe_text(_safe_dict(short.get("volatility_state")).get("volatility_regime")),
                _safe_text(_safe_dict(mid.get("volatility_state")).get("volatility_regime")),
                _safe_text(_safe_dict(long.get("volatility_state")).get("volatility_regime")),
            ),
            (
                "liquidity_risk",
                _safe_text(_safe_dict(short.get("liquidity_state")).get("liquidity_risk")),
                _safe_text(_safe_dict(mid.get("liquidity_state")).get("liquidity_risk")),
                _safe_text(_safe_dict(long.get("liquidity_state")).get("liquidity_risk")),
            ),
        ]

        def _field_status(short_v: str, mid_v: str, long_v: str) -> str:
            known = [x for x in [short_v, mid_v, long_v] if x and x != "unknown"]
            if not known:
                return "unknown"
            if len(set(known)) == 1:
                return "aligned"
            if short_v and long_v and short_v != "unknown" and long_v != "unknown" and short_v != long_v:
                return "conflicting"
            return "mixed"

        conflicts: List[Dict[str, str]] = []
        statuses: List[str] = []
        for field, short_v, mid_v, long_v in fields:
            status = _field_status(short_v, mid_v, long_v)
            statuses.append(status)
            if status == "conflicting":
                conflicts.append(
                    {
                        "field": field,
                        "short_term": short_v or "unknown",
                        "mid_term": mid_v or "unknown",
                        "long_term": long_v or "unknown",
                    }
                )

        if "conflicting" in statuses:
            alignment = "conflicting"
        elif "mixed" in statuses:
            alignment = "mixed"
        elif "aligned" in statuses:
            alignment = "aligned"
        else:
            alignment = "unknown"

        priority = {"trend": 0, "phase": 1, "volatility_regime": 2, "liquidity_risk": 3}
        conflicts = sorted(conflicts, key=lambda x: int(priority.get(str(x.get("field")), 999)))

        # 决策建议优先级：conflicting -> mixed -> aligned -> unknown
        if alignment == "conflicting":
            if any(str(x.get("field")) == "trend" for x in conflicts):
                suggested_policy = "wait_confirmation"
                policy_reason = "short_long_trend_conflict"
            else:
                suggested_policy = "reduce_risk"
                policy_reason = "multi_field_conflict"
        elif alignment == "mixed":
            suggested_policy = "reduce_risk"
            policy_reason = "timeframe_mixed"
        elif alignment == "aligned":
            suggested_policy = "follow_long_term"
            policy_reason = "timeframe_aligned"
        else:
            suggested_policy = "no_action"
            policy_reason = "insufficient_evidence"

        return {
            "alignment": alignment,
            "conflicts": conflicts,
            "suggested_policy": suggested_policy,
            "policy_reason": policy_reason,
        }

    def infer_multi_horizon_msl(self, *, features: MarketStateFeatures) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """产出多周期 MSL bundle 与跨周期冲突信息。"""
        bundle: Dict[str, Any] = {}
        bundle_meta: Dict[str, Any] = {}
        for hz in ("short_term", "mid_term", "long_term"):
            hz_features = self._build_features_for_horizon(features=features, horizon=hz)
            msl, meta = infer_msl_with_meta(features=hz_features, plugin_config=self._state_inference_config)
            bundle[hz] = msl.to_llm_dict()
            bundle_meta[hz] = dict(meta or {})
        return bundle, bundle_meta, self._build_cross_horizon(bundle)

    def build(self, *, exchange: str, symbol: str, market_structure: Dict[str, Any]) -> Tuple[MarketStateMSL, MarketStateFeatures]:
        feats0 = None
        if self._feature_store is not None:
            feats0 = self._feature_store.get(exchange, symbol)
        if feats0 is None:
            feats0 = self.aggregate_features(exchange=exchange, symbol=symbol, market_structure=market_structure)
            if self._feature_store is not None:
                self._feature_store.put(feats0)
        anomalies = self.detect_anomalies(features=feats0)
        evidence = self.extract_evidence(features=feats0, anomalies=anomalies)
        feats = MarketStateFeatures(
            exchange=feats0.exchange,
            symbol=feats0.symbol,
            ts=feats0.ts,
            horizons=feats0.horizons,
            orderbook=feats0.orderbook,
            open_interest=feats0.open_interest,
            anomalies=anomalies,
            evidence=evidence,
            derived=feats0.derived,
        )
        msl = self.infer_msl(features=feats)
        return msl, feats
