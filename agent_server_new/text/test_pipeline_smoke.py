import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent_server_new import pipeline_smoke


def test_pipeline_smoke_dry_run(capsys):
    code = pipeline_smoke.main(["--dry-run", "--exchange", "binance", "--symbol", "ETHUSDT"])
    out = capsys.readouterr().out
    assert code == 0
    assert "初始化完成" in out


def test_pipeline_smoke_run_once():
    out = asyncio.run(
        pipeline_smoke.run_pipeline_once(
            exchange="binance",
            symbol="ETHUSDT",
            signal_direction="long",
        )
    )
    assert out["action"] in {"add", "reduce", "hold", "exit", "skip"}
    assert out["direction"] in {"long", "short", "none"}

