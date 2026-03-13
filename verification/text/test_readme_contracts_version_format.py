from __future__ import annotations

import re
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verification.text.readme_contracts import README_CONTRACTS_VERSION


def test_readme_contracts_version_matches_expected_pattern() -> None:
    assert re.fullmatch(r"readme-contracts-v\d+", README_CONTRACTS_VERSION), (
        f"invalid README_CONTRACTS_VERSION: {README_CONTRACTS_VERSION}"
    )
