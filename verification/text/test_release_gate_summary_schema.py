from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verification.validators.local_refs_schema import validate_payload_with_local_refs


def test_release_gate_summary_json_matches_schema() -> None:
    proc = subprocess.run(
        ["bash", "tools/local/check_release_ready.sh", "--print-summary-only", "--summary-format", "json"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(str(proc.stdout or "{}"))
    schema_path = PROJECT_ROOT / "verification" / "reports" / "release_gate_summary_v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert validate_payload_with_local_refs(schema, payload, schema_path.parent)
