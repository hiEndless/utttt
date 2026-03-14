import sys
from pathlib import Path
import json

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import services.agent_server_new.runtime.runner as runner


class _FakeWorkflow:
    async def run(self, event):  # noqa: ANN001
        class _Plan:
            action = "skip"
            direction = "none"
            notes = "ok"

        _ = event
        return _Plan()

    async def run_with_result(self, event):  # noqa: ANN001
        class _Plan:
            action = "add"
            direction = "long"
            notes = "agent-ok"

        class _Result:
            agent_plan = _Plan()
            execution_result = {"execution_action": "reduce", "reject_reason": "position_limit_reached"}

        _ = event
        return _Result()


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


def test_runner_run_once_use_execution_result(monkeypatch, capsys):
    monkeypatch.setattr(runner, "create_trade_event_workflow_from_env", lambda: _FakeWorkflow())
    code = runner.main(
        [
            "--event-id",
            "evt-002",
            "--exchange",
            "binance",
            "--symbol",
            "ETHUSDT",
            "--signal-direction",
            "long",
            "--payload-json",
            '{"event_type":"manual_signal"}',
            "--use-execution-result",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "执行完成[execution]" in out


def test_runner_print_json(monkeypatch, capsys):
    monkeypatch.setattr(runner, "create_trade_event_workflow_from_env", lambda: _FakeWorkflow())
    code = runner.main(
        [
            "--event-id",
            "evt-003",
            "--exchange",
            "binance",
            "--symbol",
            "ETHUSDT",
            "--signal-direction",
            "long",
            "--payload-json",
            '{"event_type":"manual_signal"}',
            "--use-execution-result",
            "--print-json",
        ]
    )
    out = capsys.readouterr().out.strip()
    assert code == 0
    payload = json.loads(out)
    assert payload["source"] == "execution"
    assert payload["action"] == "reduce"


def test_runner_fail_on_execution_reject(monkeypatch, capsys):
    monkeypatch.setattr(runner, "create_trade_event_workflow_from_env", lambda: _FakeWorkflow())
    code = runner.main(
        [
            "--event-id",
            "evt-004",
            "--exchange",
            "binance",
            "--symbol",
            "ETHUSDT",
            "--signal-direction",
            "long",
            "--payload-json",
            '{"event_type":"manual_signal"}',
            "--use-execution-result",
            "--fail-on-execution-reject",
        ]
    )
    out = capsys.readouterr().out
    assert "执行完成[execution]" in out
    assert code == 2


def test_runner_prod_requires_use_execution_result(monkeypatch, capsys):
    monkeypatch.setattr(runner, "create_trade_event_workflow_from_env", lambda: _FakeWorkflow())
    monkeypatch.setenv("AGENT_RUNTIME_PROFILE", "prod")
    code = runner.main(
        [
            "--event-id",
            "evt-005",
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
    assert "requires --use-execution-result" in out
    assert code == 2
