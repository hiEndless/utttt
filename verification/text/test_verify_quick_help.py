from __future__ import annotations

import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_verify_quick_help_includes_verification_api_schema_option() -> None:
    proc = subprocess.run(
        ["bash", "tools/local/verify_quick.sh", "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--with-verification-api-schema-check" in out
    assert "--with-pipeline-mode-report" in out
    assert "--with-agent-execution-direction-intent-guard" in out
