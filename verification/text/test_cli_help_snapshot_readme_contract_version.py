from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verification.text.readme_contracts import README_CONTRACTS_DOC_ANCHOR


def test_cli_help_snapshot_contains_readme_contract_version() -> None:
    snapshot = (PROJECT_ROOT / "docs" / "operations" / "CLI_HELP_SNAPSHOT.md").read_text(encoding="utf-8")
    assert README_CONTRACTS_DOC_ANCHOR in snapshot
