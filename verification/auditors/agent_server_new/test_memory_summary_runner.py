import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import services.agent_server_new.runtime.memory_summary_runner as runner


def test_memory_summary_runner_dry_run(capsys):
    code = runner.main(
        [
            "--dry-run",
            "--limit-symbols",
            "123",
            "--summary-window",
            "77",
            "--top-risk-n",
            "9",
            "--risk-warning-min",
            "2",
            "--include-no-warning",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["dry_run"] is True
    assert payload["limit_symbols"] == 123
    assert payload["summary_window"] == 77
    assert payload["top_risk_n"] == 9
    assert payload["risk_warning_min"] == 2
    assert payload["only_risked"] is False


def test_memory_summary_runner_writes_disabled_report(tmp_path: Path, capsys):
    out_path = tmp_path / "memory_summary.latest.json"
    code = runner.main(["--output", str(out_path)])
    assert code == 0
    stdout_payload = json.loads(capsys.readouterr().out.strip())
    assert stdout_payload["schema_version"] == "symbol-memory-summary-run-v1"
    assert stdout_payload["memory_enabled"] is False
    assert out_path.is_file()
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert file_payload["schema_version"] == "symbol-memory-summary-run-v1"
    assert file_payload["report_type"] == "symbol_memory_summary"
