import argparse
import ast
import json
import sys
from typing import Any, Dict, Mapping, Optional, Sequence


def _read_text(path: Optional[str]) -> str:
    """
    读取输入：支持从文件读取，也支持从 stdin 读取。
    """
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


def _parse_signal(text: str) -> Dict[str, Any]:
    """
    将输入文本解析成 dict：
    - 优先解析为 JSON（更标准）
    - JSON 失败时，回退到 ast.literal_eval（兼容 Python dict 字面量输出）
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("输入为空：请提供 JSON 或 Python dict 文本。")
    try:
        data: Any = json.loads(text)
    except Exception:
        data = ast.literal_eval(text)
    if not isinstance(data, dict):
        raise ValueError("输入不是 dict：请提供 JSON 对象或 Python dict。")
    return data


def _to_int(value: Any) -> Optional[int]:
    """
    尝试将 value 转为 int；无法转换时返回 None。
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except Exception:
            return None
    return None


def _ensure_list(value: Any) -> Sequence[Any]:
    """
    将 value 规范化为 list；非 list/tuple 时回退为空列表。
    """
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def crop_signal(raw_signal: Mapping[str, Any]) -> Dict[str, Any]:
    """
    将原始信号裁剪为固定结构，便于下游消费。
    目标结构：
    {
      "symbol": "...",
      "timestamp": 123,
      "signal_direction": "bullish|bearish|neutral",
      "signal_context": {...}
    }
    """
    # 兼容上游可能传入非 dict 的 analysis_context
    analysis_context = raw_signal.get("analysis_context") or {}
    if not isinstance(analysis_context, dict):
        analysis_context = {}

    symbol = raw_signal.get("symbol")
    timestamp = _to_int(raw_signal.get("timestamp"))
    signal_direction = raw_signal.get("direction") or raw_signal.get("signal_direction")

    tf_hint = analysis_context.get("tf_hint") or raw_signal.get("tf_hint")
    dominant_bucket = analysis_context.get("dominant_bucket")
    supporting_buckets = analysis_context.get("supporting_buckets")
    bias = analysis_context.get("bias")
    lock_window_sec = _to_int(analysis_context.get("lock_window_sec") or raw_signal.get("lock_window_sec"))
    self_confidence = raw_signal.get("confidence") or raw_signal.get("self_confidence")
    reason_tags = analysis_context.get("reason_tags") or raw_signal.get("reason_tags")

    if not symbol:
        raise ValueError("缺少必填字段：symbol")
    if timestamp is None:
        raise ValueError("缺少必填字段：timestamp（或无法转换为整数）")
    if not signal_direction:
        raise ValueError("缺少必填字段：direction（或 signal_direction）")

    signal_context: Dict[str, Any] = {
        "tf_hint": list(_ensure_list(tf_hint)),
        "dominant_bucket": dominant_bucket,
        "supporting_buckets": list(_ensure_list(supporting_buckets)),
        "bias": bias if isinstance(bias, dict) else {},
        "lock_window_sec": lock_window_sec,
        "self_confidence": self_confidence,
        "reason_tags": list(_ensure_list(reason_tags)),
    }

    return {
        "symbol": symbol,
        "timestamp": timestamp,
        "signal_direction": signal_direction,
        "signal_context": signal_context,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将原始信号裁剪为简化结构 JSON")
    parser.add_argument("--in", dest="input_path", default=None, help="输入文件路径（不传则从 stdin 读取）")
    parser.add_argument("--out", dest="output_path", default=None, help="输出文件路径（不传则输出到 stdout）")
    parser.add_argument("--pretty", action="store_true", help="是否格式化输出（indent=2）")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    raw_text = _read_text(args.input_path)
    raw_signal = _parse_signal(raw_text)
    cropped = crop_signal(raw_signal)

    indent = 2 if args.pretty else None
    out_text = json.dumps(cropped, ensure_ascii=False, indent=indent)

    if args.output_path:
        with open(args.output_path, "w", encoding="utf-8") as f:
            f.write(out_text)
            f.write("\n")
    else:
        sys.stdout.write(out_text)
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    final_signal = {"route": "indicators", "exchange": "binance", "symbol": "ETHUSDT", "final_priority": "low",
                    "event_id": "ETHUSDT.final.1770232087150", "event_type": "market.structure",
                    "timestamp": "1770232087150", "market_state": "momentum", "direction": "bullish",
                    "confidence": "medium", "confidence_numeric": 0.5, "priority_weight": 10, "l1_total_score": 8.19,
                    "tf_hint": ["15m", "30m", "1h"],
                    "analysis_context": {"dominant_bucket": "mid", "supporting_buckets": ["mid"],
                                         "tf_hint": ["15m", "30m", "1h"], "l1_total_score": 8.19,
                                         "bias": {"short": False, "mid": True}, "reason_tags": ["high_structure_score"],
                                         "lock_window_sec": 900, "provenance": {"origin_sources": ["ind_event_engine"],
                                                                                "origin_source_hint": "indicators"},
                                         "_debug": {"scores": {"bucket_short": "0.0", "bucket_mid": "8.19",
                                                               "bucket_long": "0.0"},
                                                    "dirs": {"short": "neutral", "mid": "bullish", "long": "neutral"},
                                                    "component_scores": {"volatility": 8.19}, "indicators": [
                                                 {"plugin": "single_signal_boll", "cls": "volatility", "dir": "bullish",
                                                  "score": 5.46, "bucket": "mid", "priority": "high"}]}},
                    "meta": {"grader_version": "1.2.0",
                             "source_event_id": "binance.binance_public.ETHUSDT.single_signal_boll.1770232087150",
                             "ts_unit": "ms", "min_interval_sec": 900, "origin_source_hint": "indicators",
                             "origin_sources": ["ind_event_engine"]}, "trade_details": {}}

    cropped_signal = crop_signal(final_signal)

    print(cropped_signal)
