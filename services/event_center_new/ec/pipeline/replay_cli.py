from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from .replay import build_default_replay_tool, diff_selected


class RedisRangeClient(Protocol):
    def xrange(self, name: str, min: str = "-", max: str = "+", count: int | None = None):  # noqa: A002, ANN201
        ...

    def exists(self, name: str):  # noqa: ANN201
        ...


def _selected_schema_path() -> Path:
    here = Path(__file__).resolve()
    canonical = here.parents[2] / "docs" / "selected_event.schema.json"
    if canonical.is_file():
        return canonical
    legacy = here.parents[4] / "event_center_new" / "docs" / "selected_event.schema.json"
    if legacy.is_file():
        return legacy
    return canonical


def load_payloads_by_window(
    client: RedisRangeClient,
    *,
    stream: str,
    start_ms: int,
    end_ms: int,
    batch_size: int = 1000,
) -> list[dict[str, Any]]:
    min_id = f"{int(start_ms)}-0"
    max_id = f"{int(end_ms)}-999999"
    entries = client.xrange(stream, min=min_id, max=max_id, count=batch_size) or []
    payloads: list[dict[str, Any]] = []
    for _entry_id, fields in entries:
        raw = fields.get("payload")
        if not isinstance(raw, str):
            continue
        try:
            payloads.append(json.loads(raw))
        except Exception:
            continue
    return payloads


def run_replay_report(
    client: RedisRangeClient,
    *,
    start_ms: int,
    end_ms: int,
    raw_stream: str = "ec:raw",
    selected_stream: str = "ec:selected",
    ignore_fields: list[str] | None = None,
) -> dict[str, Any]:
    stream_presence = {
        "raw": _stream_presence(client, raw_stream),
        "selected": _stream_presence(client, selected_stream),
    }
    missing_streams = [name for name, status in stream_presence.items() if status == "missing"]
    raw_events = load_payloads_by_window(
        client,
        stream=raw_stream,
        start_ms=start_ms,
        end_ms=end_ms,
    )
    selected_online = load_payloads_by_window(
        client,
        stream=selected_stream,
        start_ms=start_ms,
        end_ms=end_ms,
    )
    tool = build_default_replay_tool()
    replay = tool.replay_from_dicts(raw_events)
    normalized_ignore_fields = [str(x).strip() for x in (ignore_fields or []) if str(x).strip()]
    replay_for_diff = _strip_fields_in_list(replay.selected, normalized_ignore_fields)
    online_for_diff = _strip_fields_in_list(selected_online, normalized_ignore_fields)
    diffs = diff_selected(replay_for_diff, online_for_diff)
    replay_signature = _stable_signature(replay_for_diff)
    online_signature = _stable_signature(online_for_diff)
    selected_contract = validate_selected_contract(selected_online)
    is_ok = (len(diffs) == 0) and selected_contract["ok"]
    return {
        "start_ms": int(start_ms),
        "end_ms": int(end_ms),
        "streams": {
            "raw": raw_stream,
            "selected": selected_stream,
        },
        "stream_presence": stream_presence,
        "missing_streams": missing_streams,
        "counts": {
            "raw_events": len(raw_events),
            "online_selected": len(selected_online),
            "replay_selected": replay.selected_count,
            "replay_layers": {
                "raw": replay.raw_count,
                "normalized": replay.normalized_count,
                "evidence": replay.evidence_count,
                "context": replay.context_count,
                "selected": replay.selected_count,
            },
        },
        "ok": is_ok,
        "ignore_fields": normalized_ignore_fields,
        "signatures": {
            "replay_selected": replay_signature,
            "online_selected": online_signature,
        },
        "selected_contract": selected_contract,
        "diffs": diffs,
        "replay_selected": replay.selected,
        "online_selected": selected_online,
    }


def format_report(report: dict[str, Any], *, pretty: bool = True) -> str:
    if pretty:
        return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    return json.dumps(report, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def event_dict_to_stream_fields(payload: dict[str, Any]) -> dict[str, str]:
    """测试辅助：把 payload 转成 Redis stream fields。"""

    return {
        "payload": json.dumps(payload, ensure_ascii=False),
        "ts_ms": str(payload.get("ts_ms", "")),
    }


def replay_result_to_dict(report: dict[str, Any]) -> dict[str, Any]:
    return asdict(report) if hasattr(report, "__dataclass_fields__") else dict(report)


def _strip_fields_in_list(items: list[dict[str, Any]], ignore_fields: list[str]) -> list[dict[str, Any]]:
    if not ignore_fields:
        return [dict(item) for item in items]
    return [_strip_fields(item, ignore_fields) for item in items]


def _strip_fields(payload: dict[str, Any], ignore_fields: list[str]) -> dict[str, Any]:
    out = json.loads(json.dumps(payload, ensure_ascii=False))
    for path in ignore_fields:
        parts = [p for p in str(path).split(".") if p]
        if not parts:
            continue
        _remove_by_path(out, parts)
    return out


def _remove_by_path(node: Any, parts: list[str]) -> None:
    if not parts:
        return
    head = parts[0]
    tail = parts[1:]
    if isinstance(node, dict):
        if head not in node:
            return
        if not tail:
            node.pop(head, None)
            return
        _remove_by_path(node.get(head), tail)
        return
    if isinstance(node, list):
        # 中文注释：列表场景下对每个元素应用同一路径，便于忽略如 trigger_event.trace.ts_ms 等字段。
        for item in node:
            _remove_by_path(item, parts)


def _stable_signature(items: list[dict[str, Any]]) -> str:
    """生成 selected 列表稳定签名，用于快速漂移对比。"""

    normalized = sorted(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in items)
    joined = "\n".join(normalized)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _stream_presence(client: RedisRangeClient, stream: str) -> str:
    """检查 stream 是否存在；无法判断时返回 unknown。"""

    exists = getattr(client, "exists", None)
    if not callable(exists):
        return "unknown"
    try:
        return "present" if int(exists(stream)) > 0 else "missing"
    except Exception:
        return "unknown"


def validate_selected_contract(items: list[dict[str, Any]]) -> dict[str, Any]:
    """校验线上 selected 顶层字段是否符合最小契约。"""

    required_fields, allowed_fields = _load_selected_contract_field_sets()
    errors: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append({"index": idx, "error": "selected_item_not_object"})
            continue
        keys = set(item.keys())
        missing = sorted(required_fields - keys)
        extra = sorted(keys - allowed_fields)
        if missing:
            errors.append({"index": idx, "error": "missing_required_fields", "fields": missing})
        if extra:
            errors.append({"index": idx, "error": "unexpected_fields", "fields": extra})
        trace = item.get("trace")
        schema_version = (trace or {}).get("schema_version") if isinstance(trace, dict) else None
        if not isinstance(schema_version, str) or (not schema_version.strip()):
            errors.append({"index": idx, "error": "missing_trace_schema_version"})
    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "required_fields": sorted(required_fields),
        "allowed_fields": sorted(allowed_fields),
        "schema_path": str(_selected_schema_path().relative_to(Path.cwd())),
    }


def _load_selected_contract_field_sets() -> tuple[set[str], set[str]]:
    schema_path = _selected_schema_path()
    try:
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        required = set(str(x) for x in (data.get("required") or []) if str(x).strip())
        allowed = set(str(k) for k in (data.get("properties") or {}).keys() if str(k).strip())
        if required and allowed:
            return required, allowed
    except Exception:
        pass
    # 中文注释：schema 读取异常时回退默认值，保证回放工具仍可给出最小契约检查。
    required = {"asset", "ts_ms", "selected_type", "direction_hint", "priority", "context_snapshot", "trace", "route"}
    allowed = required | {"trigger_event", "source", "event_ts_ms", "processed_ts_ms"}
    return required, allowed
