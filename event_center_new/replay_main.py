from __future__ import annotations

import argparse
from pathlib import Path
import sys

from event_center_new.ec.pipeline.replay_cli import format_report, run_replay_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="event_center_new 最小回放工具")
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6379/0", help="Redis 连接串")
    parser.add_argument("--start-ms", type=int, required=True, help="回放开始时间（毫秒）")
    parser.add_argument("--end-ms", type=int, required=True, help="回放结束时间（毫秒）")
    parser.add_argument("--raw-stream", default="ec:raw", help="raw stream 名称")
    parser.add_argument("--selected-stream", default="ec:selected", help="selected stream 名称")
    parser.add_argument(
        "--ignore-field",
        action="append",
        default=[],
        help="diff 时忽略字段路径（可重复），例如 ts_ms 或 trigger_event.ts_ms",
    )
    parser.add_argument("--output", default="", help="可选：把报告写入指定文件路径")
    parser.add_argument("--fail-on-contract", action="store_true", help="selected 契约不通过时返回非 0")
    parser.add_argument("--fail-on-diff", action="store_true", help="存在 diff 时返回非 0")
    parser.add_argument("--fail-on-missing-stream", action="store_true", help="检测到缺失 stream 时返回非 0")
    parser.add_argument("--compact", action="store_true", help="输出紧凑 JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        import redis  # type: ignore
    except Exception as exc:
        print("未安装 redis 依赖，无法执行回放。", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 2

    client = redis.Redis.from_url(args.redis_url, decode_responses=True)
    report = run_replay_report(
        client,
        start_ms=args.start_ms,
        end_ms=args.end_ms,
        raw_stream=args.raw_stream,
        selected_stream=args.selected_stream,
        ignore_fields=list(args.ignore_field or []),
    )
    rendered = format_report(report, pretty=not args.compact)
    print(rendered)
    output_path = str(args.output or "").strip()
    if output_path:
        Path(output_path).write_text(rendered + "\n", encoding="utf-8")
    contract_ok = bool((report.get("selected_contract") or {}).get("ok"))
    has_diff = bool(report.get("diffs"))
    missing_streams = list(report.get("missing_streams") or [])
    if args.fail_on_contract and (not contract_ok):
        return 1
    if args.fail_on_diff and has_diff:
        return 1
    if args.fail_on_missing_stream and missing_streams:
        return 1
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
