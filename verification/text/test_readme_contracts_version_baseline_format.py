from __future__ import annotations

import re
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_readme_contracts_version_baseline_has_single_effective_line() -> None:
    baseline_path = PROJECT_ROOT / "verification" / "text" / "readme_contracts_version.baseline"
    lines = [line.strip() for line in baseline_path.read_text(encoding="utf-8").splitlines()]
    effective = [line for line in lines if line and not line.startswith("#")]
    assert len(effective) == 1, f"baseline must have exactly one effective version line: {effective}"
    assert re.fullmatch(r"readme-contracts-v\d+", effective[0]), f"invalid baseline version: {effective[0]}"
