import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import agent_server_new.runner as runner


class _FakeWorkflow:
    async def run(self, event):  # noqa: ANN001
        class _Plan:
            action = "skip"
            direction = "none"
            notes = "ok"

        _ = event
        return _Plan()


def test_runner_dry_run(monkeypatch, capsys):
    monkeypatch.setattr(runner, "create_trade_event_workflow_from_env", lambda: _FakeWorkflow())
    code = runner.main(["--dry-run", "--exchange", "binance", "--symbol", "ETHUSDT"])
    out = capsys.readouterr().out
    assert code == 0
    assert "初始化成功" in out


def test_runner_run_once(monkeypatch, capsys):
    monkeypatch.setattr(runner, "create_trade_event_workflow_from_env", lambda: _FakeWorkflow())
    code = runner.main(
        [
            "--event-id",
            "evt-001",
            "--exchange",
            "binance",
            "--symbol",
            "ETHUSDT",
            "--signal-direction",
            "long",
            "--payload-json",
            '{"event_type":"manual_signal"}',
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "执行完成" in out

