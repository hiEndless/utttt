from __future__ import annotations

import argparse
import sys

from event_center_new.ec.pipeline.replay_cli import format_report, run_replay_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="event_center_new 最小回放工具")
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6379/0", help="Redis 连接串")
    parser.add_argument("--start-ms", type=int, required=True, help="回放开始时间（毫秒）")
    parser.add_argument("--end-ms", type=int, required=True, help="回放结束时间（毫秒）")
    parser.add_argument("--raw-stream", default="ec:raw", help="raw stream 名称")
    parser.add_argument("--selected-stream", default="ec:selected", help="selected stream 名称")
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
    )
    print(format_report(report, pretty=not args.compact))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
