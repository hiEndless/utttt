from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
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


async def _run_once(*, limit_symbols: int, summary_window: int) -> int:
    adapter = _create_memory_adapter_from_env()
    if adapter is None:
        print("symbol_memory_disabled")
        return 0
    result = await run_symbol_memory_summary_once(
        maintenance=adapter,
        limit_symbols=limit_symbols,
        summary_window=summary_window,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if bool(result.get("ok")) else 2


async def _run_loop(*, interval_s: float, limit_symbols: int, summary_window: int) -> int:
    while True:
        code = await _run_once(limit_symbols=limit_symbols, summary_window=summary_window)
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
            )
        )
    return asyncio.run(
        _run_once(
            limit_symbols=int(args.limit_symbols),
            summary_window=int(args.summary_window),
        )
    )


if __name__ == "__main__":
    sys.exit(main())
