from __future__ import annotations

import re
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verification.text.readme_contracts import README_CONTRACTS_VERSION


def _parse_version(value: str) -> int:
    m = re.fullmatch(r"readme-contracts-v(\d+)", value.strip())
    assert m, f"invalid version format: {value}"
    return int(m.group(1))


def test_readme_contracts_version_not_lower_than_baseline() -> None:
    baseline_path = PROJECT_ROOT / "verification" / "text" / "readme_contracts_version.baseline"
    baseline_raw = baseline_path.read_text(encoding="utf-8").strip()
    current_ver = _parse_version(README_CONTRACTS_VERSION)
    baseline_ver = _parse_version(baseline_raw)
    assert current_ver >= baseline_ver, (
        f"README_CONTRACTS_VERSION regressed: current={README_CONTRACTS_VERSION} baseline={baseline_raw}"
    )
