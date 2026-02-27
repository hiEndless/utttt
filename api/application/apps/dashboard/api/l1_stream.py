from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, Query

from ...account.views import get_current_user_id
from ....common.redis_client import get_async_redis_client
from ....common.status_codes import BaseResponse, BusinessException, StatusCode, success_response

router = APIRouter(tags=["Dashboard - L1 Stream"])
logger = logging.getLogger(__name__)


def _try_parse_json(value: Any) -> Any:
    """尝试将 Redis 字符串值解析为 JSON；解析失败则原样返回"""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    s = value.strip()
    if not s:
        return value
    try:
        return json.loads(s)
    except Exception:
        return value


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    s = str(value or "").strip().lower()
    if s in ("true", "1", "yes", "y", "on"):
        return True
    if s in ("false", "0", "no", "n", "off"):
        return False
    return default


def _pick_top_components(component_scores: Any, top_k: int = 3) -> list[dict[str, Any]]:
    """
    组件分数用于展示“主要驱动因素”，这里仅保留绝对值最大的前 N 个，减少前端负担。
    component_scores 期望为 dict[cls]->score。
    """
    if not isinstance(component_scores, dict):
        return []
    items = []
    for k, v in component_scores.items():
        items.append({"component": k, "score": _safe_float(v, 0.0)})
    items.sort(key=lambda x: abs(float(x.get("score") or 0.0)), reverse=True)
    return items[: max(0, int(top_k))]


def _normalize_symbol(value: Any) -> str:
    """
    符号标准化：统一大写，并移除常见分隔符，避免前端传 ETH/USDT、ETH-USDT 等导致无法匹配。
    仅用于“展示层过滤”，不改变 Redis 内实际写入值。
    """
    s = str(value or "").strip().upper()
    if not s:
        return ""
    return "".join(ch for ch in s if ch.isalnum())


def _extract_plugins(indicator_values: Any, top_k: int = 3) -> list[str]:
    """
    从 L1 的 indicator_values 明细中提取插件来源（如 single_signal_williams_r），用于前端展示事件来源。
    规则：按绝对分数从高到低，去重后取前 N 个。
    """
    if not isinstance(indicator_values, list):
        return []
    scored: list[tuple[float, str]] = []
    for it in indicator_values:
        if not isinstance(it, dict):
            continue
        name = str(it.get("plugin") or "").strip()
        if not name:
            continue
        score = _safe_float(it.get("score"), 0.0)
        scored.append((abs(score), name))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[str] = []
    seen = set()
    for _, name in scored:
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= max(0, int(top_k)):
            break
    return out


def _simplify_l1_entry(entry_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    component_scores = _try_parse_json(fields.get("component_scores"))
    indicator_values = _try_parse_json(fields.get("indicator_values"))
    plugins = _extract_plugins(indicator_values, top_k=3)
    return {
        "id": entry_id,
        "timestamp": _safe_int(fields.get("timestamp")),
        "symbol": fields.get("symbol") or "",
        "stage": "l1",
        "direction": fields.get("direction") or "neutral",
        "market_state": fields.get("market_state") or "range",
        "result_priority": fields.get("result_priority") or "low",
        "total_score": _safe_float(fields.get("total_score")),
        "short_term_bias": _safe_bool(fields.get("short_term_bias")),
        "mid_term_bias": _safe_bool(fields.get("mid_term_bias")),
        "short_dir": fields.get("short_dir") or "neutral",
        "mid_dir": fields.get("mid_dir") or "neutral",
        "long_dir": fields.get("long_dir") or "neutral",
        "bucket_short_score": _safe_float(fields.get("bucket_short_score")),
        "bucket_mid_score": _safe_float(fields.get("bucket_mid_score")),
        "bucket_long_score": _safe_float(fields.get("bucket_long_score")),
        "origin_source_hint": fields.get("origin_source_hint") or "unknown",
        "plugin": plugins[0] if plugins else "",
        # "plugins": plugins,
        "top_components": _pick_top_components(component_scores, top_k=3),
    }


@router.get(
    "/dashboard/l1_stream/{exchange}/{symbol}",
    response_model=BaseResponse[Any],
)
async def get_l1_stream(
    exchange: str,
    symbol: str,
    limit: int = Query(50, ge=1, le=500, description="返回的最新消息条数（按 symbol 过滤后）"),
    cursor: str | None = Query(None, description="游标（Redis Stream entry id）；用于分页继续读取"),
    direction: str = Query("backward", pattern="^(backward|forward)$", description="分页方向：backward=从新到旧；forward=从旧到新"),
    scan_factor: int = Query(10, ge=1, le=50, description="扫描倍率：用于从全局流中过滤出指定 symbol 的记录"),
    debug: bool = Query(False, description="是否返回调试信息（仅用于排障）"),
    user_id: str = Depends(get_current_user_id),
):
    """
    读取 Redis Stream（L1 聚合层）数据，并按 symbol 过滤记录用于前端展示。

    说明：
    - event_center 的 L1 输出流默认是全局流（不是按 symbol 分流），因此这里需要“扫描+过滤”。
    - 为了前端展示，只输出少量字段，且对 JSON 字段做容错解析与精简。
    """
    redis_client = get_async_redis_client()
    stream_key = os.getenv("L1_STREAM", "l1_events")

    try:
        exists = await redis_client.exists(stream_key)
    except Exception:
        logger.exception("检查 Redis key 是否存在失败：key=%s", stream_key)
        raise BusinessException(code=StatusCode.SERVER_ERROR, message="读取 Redis 失败")

    if not exists:
        raise BusinessException(
            code=StatusCode.NOT_FOUND,
            message="L1 Stream 数据不存在",
        )

    target_symbol = _normalize_symbol(symbol)
    if not target_symbol:
        raise BusinessException(code=StatusCode.PARAM_ERROR, message="symbol 不能为空")

    out: list[dict[str, Any]] = []
    next_cursor: str | None = cursor
    debug_info: dict[str, Any] = {"stream_key": stream_key} if debug else {}
    scanned_count = 0
    matched_count = 0

    batch_count = min(2000, max(50, int(limit) * int(scan_factor)))
    max_rounds = 10

    try:
        for _ in range(max_rounds):
            if direction == "forward":
                entries = await redis_client.xrange(stream_key, min=next_cursor or "-", max="+", count=batch_count)
                if next_cursor and entries and entries[0][0] == next_cursor:
                    entries = entries[1:]
            else:
                entries = await redis_client.xrevrange(stream_key, max=next_cursor or "+", min="-", count=batch_count)
                if next_cursor and entries and entries[0][0] == next_cursor:
                    entries = entries[1:]

            if not entries:
                break

            last_seen_id: str | None = None

            for entry_id, fields in entries:
                last_seen_id = str(entry_id)
                scanned_count += 1
                if isinstance(fields, dict):
                    decoded = {}
                    for k, v in fields.items():
                        kk = k.decode() if isinstance(k, (bytes, bytearray)) else str(k)
                        vv = v.decode() if isinstance(v, (bytes, bytearray)) else v
                        decoded[kk] = vv
                else:
                    decoded = {}

                if _normalize_symbol(decoded.get("symbol")) != target_symbol:
                    continue

                matched_count += 1
                out.append(_simplify_l1_entry(str(entry_id), decoded))
                if len(out) >= int(limit):
                    break

            if last_seen_id is not None:
                next_cursor = last_seen_id

            if len(out) >= int(limit):
                break

        if direction == "forward":
            out.sort(key=lambda x: int(x.get("timestamp") or 0))
        else:
            out.sort(key=lambda x: int(x.get("timestamp") or 0), reverse=True)
    except BusinessException:
        raise
    except Exception:
        logger.exception("读取 L1 Stream 失败：key=%s cursor=%s direction=%s", stream_key, cursor, direction)
        raise BusinessException(code=StatusCode.SERVER_ERROR, message="读取 Redis 失败")

    if debug:
        debug_info.update(
            {
                "target_symbol": target_symbol,
                "scanned_count": scanned_count,
                "matched_count": matched_count,
                "batch_count": batch_count,
                "max_rounds": max_rounds,
            }
        )
        return success_response({"items": out, "next_cursor": next_cursor, "direction": direction, "debug": debug_info})
    return success_response({"items": out, "next_cursor": next_cursor, "direction": direction})
