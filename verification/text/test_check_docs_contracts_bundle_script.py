from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_check_docs_contracts_bundle_script_logs_readme_contract_version() -> None:
    script = (PROJECT_ROOT / "tools" / "local" / "check_docs_contracts_bundle.sh").read_text(encoding="utf-8")
    assert "README_CONTRACTS_VERSION" in script
    assert "[info] README_CONTRACTS_VERSION=" in script
