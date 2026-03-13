from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verification.text.readme_contracts import _normalize_doc_path
from verification.text.readme_contracts import get_required_snippets_for_doc


def test_normalize_doc_path_keeps_relative_shape() -> None:
    assert _normalize_doc_path(Path("services/agent_server_new/README.md")) == Path("services/agent_server_new/README.md")


def test_normalize_doc_path_collapses_backslashes() -> None:
    raw = Path("services\\agent_server_new\\README.md")
    assert _normalize_doc_path(raw) == Path("services/agent_server_new/README.md")


def test_get_required_snippets_for_unknown_doc_returns_empty_tuple() -> None:
    unknown = Path("docs/not_exists.md")
    assert get_required_snippets_for_doc(unknown) == ()
