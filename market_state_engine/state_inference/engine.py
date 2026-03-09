from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

from market_state_engine.contracts import MarketStateMSL

from .base import StateInferencePlugin
from .liquidity_inference import LiquidityInferencePlugin
from .msl_generator import build_msl, get_supported_inference_versions
from .positioning_inference import PositioningInferencePlugin
from .risk_inference import RiskInferencePlugin
from .rule_regime_inference import RuleRegimeInferencePlugin
from .state_fusion import run_plugins
from .structure_inference import StructureInferencePlugin
from .volatility_inference import VolatilityInferencePlugin

if TYPE_CHECKING:
    from market_state_engine.engine import MarketStateFeatures


_PLUGIN_PROFILES: Dict[str, List[str]] = {
    # 全量推断：保持当前默认行为
    "default": [
        "regime_inference",
        "positioning_inference",
        "volatility_inference",
        "liquidity_inference",
        "risk_inference",
        "structure_inference",
    ],
    # 轻量模式：保留核心方向与风险，不做结构细化
    "fast_mode": [
        "regime_inference",
        "positioning_inference",
        "volatility_inference",
        "liquidity_inference",
        "risk_inference",
    ],
    # 风险模式：最小化依赖，仅输出风险相关主链路
    "risk_only": [
        "regime_inference",
        "risk_inference",
    ],
}


def _default_profiles_file() -> str:
    return str(Path(__file__).resolve().parents[1] / "config" / "state_inference_profiles.json")


def _load_profiles_from_file(path: str) -> Dict[str, List[str]]:
    """从 JSON 文件加载 profiles；失败时返回空字典由上层回退。"""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}

    out: Dict[str, List[str]] = {}
    for k, v in payload.items():
        if not isinstance(k, str):
            continue
        if not isinstance(v, list):
            continue
        out[k] = [str(x) for x in v if x]
    return out


def _resolve_profiles(plugin_config: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    if not isinstance(plugin_config, dict):
        file_profiles = _load_profiles_from_file(_default_profiles_file())
        return file_profiles or _PLUGIN_PROFILES
    inline_profiles = plugin_config.get("plugin_profiles")
    if isinstance(inline_profiles, dict):
        out: Dict[str, List[str]] = {}
        for k, v in inline_profiles.items():
            if isinstance(k, str) and isinstance(v, list):
                out[k] = [str(x) for x in v if x]
        if out:
            return out
    profiles_file = str(plugin_config.get("profiles_file") or "").strip() or _default_profiles_file()
    file_profiles = _load_profiles_from_file(profiles_file)
    return file_profiles or _PLUGIN_PROFILES


def default_plugins() -> List[StateInferencePlugin]:
    # 插件顺序即推断依赖拓扑，必须稳定。
    return [
        RuleRegimeInferencePlugin(),
        PositioningInferencePlugin(),
        VolatilityInferencePlugin(),
        LiquidityInferencePlugin(),
        RiskInferencePlugin(),
        StructureInferencePlugin(),
    ]


def _build_plugins_from_config(plugin_config: Optional[Dict[str, Any]]) -> List[StateInferencePlugin]:
    """根据配置构建插件列表。

    支持字段：
    - plugin_profile: 预设插件配置（default/fast_mode/risk_only）
    - enabled_plugins: 仅启用名单（为空则默认启用全部）
    - disabled_plugins: 禁用名单
    """
    defaults = default_plugins()
    if not isinstance(plugin_config, dict):
        plugin_config = {}

    profile = str(plugin_config.get("plugin_profile") or "default").strip() or "default"
    profiles = _resolve_profiles(plugin_config)
    enabled_raw = plugin_config.get("enabled_plugins")
    disabled_raw = plugin_config.get("disabled_plugins")
    profile_enabled = set(profiles.get(profile, profiles.get("default", [])))
    enabled = {str(x) for x in list(enabled_raw or []) if x}
    disabled = {str(x) for x in list(disabled_raw or []) if x}

    out: List[StateInferencePlugin] = []
    for plugin in defaults:
        name = str(getattr(plugin, "name", ""))
        # 优先级：enabled_plugins > plugin_profile > default
        if enabled:
            allow = name in enabled
        else:
            allow = name in profile_enabled
        if not allow:
            continue
        if name in disabled:
            continue
        out.append(plugin)
    return out


def infer_msl_from_features(
    *,
    features: "MarketStateFeatures",
    plugins: Optional[Sequence[StateInferencePlugin]] = None,
    plugin_config: Optional[Dict[str, Any]] = None,
) -> MarketStateMSL:
    msl, _meta = infer_msl_with_meta(features=features, plugins=plugins, plugin_config=plugin_config)
    return msl


def infer_msl_with_meta(
    *,
    features: "MarketStateFeatures",
    plugins: Optional[Sequence[StateInferencePlugin]] = None,
    plugin_config: Optional[Dict[str, Any]] = None,
) -> Tuple[MarketStateMSL, Dict[str, Any]]:
    cfg = plugin_config if isinstance(plugin_config, dict) else {}
    used_plugins = list(plugins) if plugins is not None else _build_plugins_from_config(plugin_config)
    state, plugin_evidence, warnings = run_plugins(plugins=used_plugins, features=features)
    inference_version_req = str(cfg.get("inference_version") or "msl_generator_v1")
    msl, inference_version_used = build_msl(
        features=features,
        state=state,
        plugin_evidence=plugin_evidence,
        warnings=warnings,
        inference_version=inference_version_req,
    )
    profile = str(cfg.get("plugin_profile") or "default")
    meta = {
        "schema_version": int(msl.version),
        "inference_version": inference_version_used,
        "inference_version_requested": inference_version_req,
        "inference_profile": profile,
        "supported_inference_versions": get_supported_inference_versions(),
    }
    return msl, meta
