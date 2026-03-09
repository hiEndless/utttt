"""
market_structure.holding_context

用于计算持仓相关的上下文字段（holding_context），使其可独立于聚合输出层复用。
后续可直接迁移到 agent 服务层作为通用工具模块。
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

SHORT_TERM_MAX_MS = 8 * 60 * 60 * 1000
MID_TERM_MAX_MS = 24 * 60 * 60 * 1000


def format_duration_ms(duration_ms: int) -> str:
    """将毫秒时长格式化为紧凑的人类可读串（例如 2h15m）。"""
    ms = max(0, int(duration_ms))
    s = ms // 1000
    m = s // 60
    h = m // 60
    d = h // 24
    m = m % 60
    h = h % 24

    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m or not parts:
        parts.append(f"{m}m")
    return "".join(parts)


def match_horizon_by_duration(duration_ms: int) -> str:
    """根据持仓时长（毫秒）匹配 horizon。"""
    ms = max(0, int(duration_ms))
    if ms <= SHORT_TERM_MAX_MS:
        return "short_term"
    if ms <= MID_TERM_MAX_MS:
        return "mid_term"
    return "long_term"


def build_holding_context(holding_until_ts_ms: int, now_ts_ms: Optional[int] = None) -> Dict[str, Any]:
    """构建 holding_context。

    参数：
    - holding_until_ts_ms：外部传入的目标时间戳（毫秒）
    - now_ts_ms：可选；用于离线回放/测试时固定当前时间
    """
    now_ms = int(now_ts_ms if now_ts_ms is not None else time.time() * 1000)
    duration_ms = int(now_ms) - int(holding_until_ts_ms)
    duration_ms = max(0, int(duration_ms))
    horizon = match_horizon_by_duration(duration_ms)
    return {
        "now_ts_ms": now_ms,
        "holding_until_ts_ms": int(holding_until_ts_ms),
        "duration_ms": int(duration_ms),
        "duration_human": format_duration_ms(duration_ms),
        "horizon": horizon,
    }


def main(holding_until_ts_ms: Optional[int] = None) -> None:
    now_ms = int(time.time() * 1000)
    holding_until_ts_ms = int(holding_until_ts_ms if holding_until_ts_ms is not None else (now_ms + 3 * 60 * 60 * 1000))
    out = build_holding_context(holding_until_ts_ms, now_ts_ms=now_ms)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

