from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GUARD_SCRIPT = PROJECT_ROOT / "tools" / "local" / "check_direction_enum_doc_guard.sh"


def test_check_direction_enum_doc_guard_passes() -> None:
    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[passed] direction enum doc guard" in result.stdout
