from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from services.agent_server_new.adapters.symbol_memory_inmemory import InMemorySymbolMemoryAdapter
from services.agent_server_new.adapters.symbol_memory_redis import (
    RedisSymbolMemoryAdapter,
    RedisSymbolMemoryConfig,
    create_redis_client_from_env,
)
from services.agent_server_new.app.jobs.symbol_memory_summary_job import run_symbol_memory_summary_once


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="agent_server_new symbol memory summary runner")
    p.add_argument("--dry-run", action="store_true", help="仅打印配置并退出")
    p.add_argument("--loop", action="store_true", help="循环执行 summary 任务")
    p.add_argument("--interval-s", type=float, default=60.0, help="循环模式下执行间隔（秒）")
    p.add_argument("--limit-symbols", type=int, default=1000, help="每轮最多处理的 symbol 数")
    p.add_argument("--summary-window", type=int, default=50, help="每个 symbol 用于 summary 的 raw 窗口")
    p.add_argument("--top-risk-n", type=int, default=5, help="输出 contract_warning_count 最高的 symbol TopN")
    p.add_argument("--risk-warning-min", type=int, default=1, help="仅纳入 contract_warning_count >= 该阈值的 symbol")
    p.add_argument("--include-no-warning", action="store_true", help="高风险简报中包含 0 告警 symbol（默认仅输出有告警）")
    p.add_argument("--output", default="", help="可选：将本次结果写入 JSON 文件")
    return p


def _create_memory_adapter_from_env() -> Any:
    enabled = str(os.getenv("AGENT_SYMBOL_MEMORY_ENABLED", "false") or "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not enabled:
        return None

    backend = str(os.getenv("AGENT_SYMBOL_MEMORY_BACKEND", "inmemory") or "inmemory").strip().lower()
    if backend == "redis":
        cfg = RedisSymbolMemoryConfig.from_env()
        redis_client = create_redis_client_from_env(cfg.redis_url)
        return RedisSymbolMemoryAdapter(
            redis_client=redis_client,
            raw_key_template=cfg.raw_key_template,
            summary_key_template=cfg.summary_key_template,
            symbol_index_key=cfg.symbol_index_key,
            ttl_seconds=cfg.ttl_seconds,
            raw_topk=cfg.raw_topk,
        )
    return InMemorySymbolMemoryAdapter()


def _write_output_if_needed(*, output: str, payload: dict[str, Any]) -> None:
    path = str(output or "").strip()
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def _run_once(
    *,
    limit_symbols: int,
    summary_window: int,
    top_risk_n: int,
    risk_warning_min: int,
    only_risked: bool,
    output: str,
) -> int:
    adapter = _create_memory_adapter_from_env()
    if adapter is None:
        now_ms = int(time.time() * 1000)
        result = {
            "schema_version": "symbol-memory-summary-run-v1",
            "report_type": "symbol_memory_summary",
            "memory_enabled": False,
            "ok": True,
            "total_symbols": 0,
            "success_symbols": 0,
            "failed_symbols": 0,
            "summary_window": int(summary_window),
            "started_ms": now_ms,
            "ended_ms": now_ms,
            "duration_ms": 0,
            "last_error": "",
            "high_risk_symbols": [],
            "risk_warning_min": int(risk_warning_min),
            "only_risked": bool(only_risked),
        }
        print(json.dumps(result, ensure_ascii=False))
        _write_output_if_needed(output=output, payload=result)
        return 0
    result = await run_symbol_memory_summary_once(
        maintenance=adapter,
        limit_symbols=limit_symbols,
        summary_window=summary_window,
        top_risk_n=top_risk_n,
        risk_warning_min=risk_warning_min,
        only_risked=only_risked,
    )
    print(json.dumps(result, ensure_ascii=False))
    _write_output_if_needed(output=output, payload=result)
    return 0 if bool(result.get("ok")) else 2


async def _run_loop(
    *,
    interval_s: float,
    limit_symbols: int,
    summary_window: int,
    top_risk_n: int,
    risk_warning_min: int,
    only_risked: bool,
    output: str,
) -> int:
    while True:
        code = await _run_once(
            limit_symbols=limit_symbols,
            summary_window=summary_window,
            top_risk_n=top_risk_n,
            risk_warning_min=risk_warning_min,
            only_risked=only_risked,
            output=output,
        )
        if code != 0:
            return code
        await asyncio.sleep(max(1.0, float(interval_s)))


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.dry_run:
        payload = {
            "dry_run": True,
            "loop": bool(args.loop),
            "interval_s": float(args.interval_s),
            "limit_symbols": int(args.limit_symbols),
            "summary_window": int(args.summary_window),
            "top_risk_n": int(args.top_risk_n),
            "risk_warning_min": int(args.risk_warning_min),
            "only_risked": not bool(args.include_no_warning),
            "output": str(args.output or ""),
            "memory_enabled": str(os.getenv("AGENT_SYMBOL_MEMORY_ENABLED", "false")),
            "memory_backend": str(os.getenv("AGENT_SYMBOL_MEMORY_BACKEND", "inmemory")),
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    if args.loop:
        return asyncio.run(
            _run_loop(
                interval_s=float(args.interval_s),
                limit_symbols=int(args.limit_symbols),
                summary_window=int(args.summary_window),
                top_risk_n=int(args.top_risk_n),
                risk_warning_min=int(args.risk_warning_min),
                only_risked=not bool(args.include_no_warning),
                output=str(args.output or ""),
            )
        )
    return asyncio.run(
        _run_once(
            limit_symbols=int(args.limit_symbols),
            summary_window=int(args.summary_window),
            top_risk_n=int(args.top_risk_n),
            risk_warning_min=int(args.risk_warning_min),
            only_risked=not bool(args.include_no_warning),
            output=str(args.output or ""),
        )
    )


if __name__ == "__main__":
    sys.exit(main())
