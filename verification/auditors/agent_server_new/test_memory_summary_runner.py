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
