import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import agent_server_new.memory_summary_runner as runner


def test_memory_summary_runner_dry_run(capsys):
    code = runner.main(["--dry-run", "--limit-symbols", "123", "--summary-window", "77"])
    assert code == 0
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["dry_run"] is True
    assert payload["limit_symbols"] == 123
    assert payload["summary_window"] == 77
