import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent_server_new.adapters.symbol_memory_inmemory import InMemorySymbolMemoryAdapter
from agent_server_new.app.jobs.symbol_memory_summary_job import run_symbol_memory_summary_once


def test_run_symbol_memory_summary_once():
    async def _run():
        memory = InMemorySymbolMemoryAdapter()
        await memory.record_symbol_memory(
            "binance",
            "ETHUSDT",
            {
                "ts": 1000,
                "event_id": "evt-1",
                "signal": {"direction": "long", "verdict": "accept"},
                "plan": {"action": "add", "direction": "long"},
            },
        )
        await memory.record_symbol_memory(
            "binance",
            "BTCUSDT",
            {
                "ts": 1100,
                "event_id": "evt-2",
                "signal": {"direction": "short", "verdict": "accept"},
                "plan": {"action": "add", "direction": "short"},
            },
        )

        result = await run_symbol_memory_summary_once(
            maintenance=memory,
            limit_symbols=10,
            summary_window=20,
        )
        assert result["ok"] is True
        assert result["total_symbols"] == 2
        assert result["success_symbols"] == 2

        eth = await memory.get_symbol_memory("binance", "ETHUSDT", limit=3)
        btc = await memory.get_symbol_memory("binance", "BTCUSDT", limit=3)
        assert eth["summary"]["trend_bias"] == "bullish"
        assert btc["summary"]["trend_bias"] == "bearish"

    asyncio.run(_run())
