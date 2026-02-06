from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


def _safe_float(value: Any, default: float = 0.0) -> float:
    """将输入尽可能安全地转成 float。"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except Exception:
            return default
    try:
        return float(value)
    except Exception:
        return default


def _normalize_direction(value: Any) -> Optional[str]:
    """标准化方向字段到 bullish/bearish/neutral/unclear。"""
    if not value:
        return None
    v = str(value).strip().lower()
    if v in {"bullish", "bearish", "neutral", "unclear"}:
        return v
    if v in {"long", "up", "bull"}:
        return "bullish"
    if v in {"short", "down", "bear"}:
        return "bearish"
    if v in {"unknown"}:
        return "unclear"
    return None


def _extract_signal_direction(signal: Optional[Mapping[str, Any]]) -> Optional[str]:
    """从信号/方向假设对象里提取方向。"""
    if not isinstance(signal, Mapping):
        return None
    direct = _normalize_direction(signal.get("directional_context"))
    if direct:
        return direct
    direct = _normalize_direction(signal.get("signal_direction"))
    if direct:
        return direct
    direct = _normalize_direction(signal.get("direction"))
    if direct:
        return direct
    final_event = signal.get("final_event")
    if isinstance(final_event, Mapping):
        direct = _normalize_direction(final_event.get("direction"))
        if direct:
            return direct
    return None


def derive_directional_reference(
    signal: Optional[Mapping[str, Any]],
    market_structure: Optional[Mapping[str, Any]],
) -> str:
    """
    推导当前决策上下文的方向参考锚点（不看仓位）。

    目标输出：bullish / bearish / neutral / unclear
    """
    signal_dir = _extract_signal_direction(signal)
    verdict = str(signal.get("verdict") or "").upper() if isinstance(signal, Mapping) else ""
    alignment = str(signal.get("structural_alignment") or "").upper() if isinstance(signal, Mapping) else ""

    if signal_dir:
        if verdict == "ALLOW":
            if not alignment or alignment == "ALIGNED":
                return signal_dir
            return "neutral"
        if verdict in {"ATTENUATE", "BLOCK"}:
            return "neutral"
        return signal_dir

    pre = market_structure.get("pre_decision_structure") if isinstance(market_structure, Mapping) else None
    if not isinstance(pre, Mapping):
        return "unclear"

    def _extract_from_hz(hz_key: str) -> Tuple[str, str]:
        hz = pre.get(hz_key)
        if not isinstance(hz, Mapping):
            return "", ""
        pp = hz.get("participant_positioning")
        if not isinstance(pp, Mapping):
            return "", ""
        structural_weight = str(pp.get("structural_weight") or "")
        inf = pp.get("participant_inference")
        if not isinstance(inf, Mapping):
            return structural_weight, ""
        positioning_mode = str(inf.get("positioning_mode") or "")
        return structural_weight, positioning_mode

    candidates: List[Tuple[str, str]] = []
    for hz_key in ("mid_term", "short_term"):
        w, mode = _extract_from_hz(hz_key)
        if w or mode:
            candidates.append((w, mode))

    if not candidates:
        return "unclear"

    dominant = next((c for c in candidates if c[0] == "high"), candidates[0])
    positioning_mode = str(dominant[1] or "").lower()
    if positioning_mode == "risk_on":
        return "bullish"
    if positioning_mode in {"risk_off", "neutral"}:
        return "neutral"
    if positioning_mode == "unclear":
        return "unclear"
    return "unclear"


def derive_holding_bias(position_side: Any, directional_reference: str) -> str:
    """
    基于“方向一致性”计算 holding_bias。

    - aligned：持仓方向顺应当前方向锚点
    - against：持仓方向与当前方向锚点相反
    - neutral：方向锚点为 neutral/unclear 时，不做顺逆判断
    """
    ref = _normalize_direction(directional_reference) or "unclear"
    if ref in {"neutral", "unclear"}:
        return "neutral"

    side = str(position_side or "").upper()
    if ref == "bullish" and side == "LONG":
        return "aligned"
    if ref == "bearish" and side == "SHORT":
        return "aligned"
    if side in {"LONG", "SHORT"}:
        return "against"
    return "neutral"


def derive_exposure_level(
    position: Mapping[str, Any],
    thresholds: Tuple[float, float] = (100.0, 500.0),
) -> str:
    """
    将仓位规模映射到 small / medium / large。

    默认按 notional（名义价值）分档；若缺失则退化用 initialMargin。
    thresholds = (small_max, medium_max)
    """
    small_max, medium_max = thresholds
    notional = abs(_safe_float(position.get("notional"), default=0.0))
    if notional <= 0.0:
        notional = abs(_safe_float(position.get("initialMargin"), default=0.0))

    if notional < small_max:
        return "small"
    if notional < medium_max:
        return "medium"
    return "large"


def derive_pnl_state(
    pnl_ratio: Any,
    flat_abs_threshold: float = 0.001,
    large_profit_threshold: float = 0.01,
) -> str:
    """将 pnl_ratio 映射到 loss / flat / small_profit / large_profit。"""
    r = _safe_float(pnl_ratio, default=0.0)
    if abs(r) < flat_abs_threshold:
        return "flat"
    if r < 0:
        return "loss"
    if r >= large_profit_threshold:
        return "large_profit"
    return "small_profit"


def transform_positions_to_decision_context(
    positions: Optional[Iterable[Mapping[str, Any]]],
    *,
    signal: Optional[Mapping[str, Any]] = None,
    market_structure: Optional[Mapping[str, Any]] = None,
    exposure_thresholds: Tuple[float, float] = (100.0, 500.0),
    flat_abs_threshold: float = 0.001,
    large_profit_threshold: float = 0.01,
) -> List[Dict[str, Any]]:
    """
    将 positions 列表转成决策层可直接消费的持仓派生状态列表。

    输出单元结构：
    {
      "position_side": "LONG",
      "exposure_level": "small|medium|large",
      "pnl_state": "loss|flat|small_profit|large_profit",
      "holding_bias": "aligned|against|neutral"
    }
    """
    directional_reference = derive_directional_reference(signal, market_structure)
    out: List[Dict[str, Any]] = []
    for p in list(positions or []):
        if not isinstance(p, Mapping):
            continue
        position_side = str(p.get("position_side") or "").upper()
        if position_side not in {"LONG", "SHORT"}:
            continue
        out.append(
            {
                "position_side": position_side,
                "exposure_level": derive_exposure_level(p, thresholds=exposure_thresholds),
                "pnl_state": derive_pnl_state(
                    p.get("pnl_ratio"),
                    flat_abs_threshold=flat_abs_threshold,
                    large_profit_threshold=large_profit_threshold,
                ),
                "holding_bias": derive_holding_bias(position_side, directional_reference),
            }
        )
    return out

