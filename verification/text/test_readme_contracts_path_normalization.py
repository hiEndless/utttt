from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verification.text.readme_contracts import _normalize_doc_path


def test_normalize_doc_path_keeps_relative_shape() -> None:
    assert _normalize_doc_path(Path("services/agent_server_new/README.md")) == Path("services/agent_server_new/README.md")


def test_normalize_doc_path_collapses_backslashes() -> None:
    raw = Path("services\\agent_server_new\\README.md")
    assert _normalize_doc_path(raw) == Path("services/agent_server_new/README.md")
