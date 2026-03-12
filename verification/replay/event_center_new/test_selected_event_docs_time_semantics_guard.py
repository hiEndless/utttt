from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_event_center_pipeline_doc_declares_selected_event_time_split() -> None:
    path = Path(PROJECT_ROOT) / "docs" / "contracts" / "pipelines" / "event_center_new_data_contracts.md"
    text = path.read_text(encoding="utf-8")
    assert "event_ts_ms" in text
    assert "processed_ts_ms" in text
    assert "ts_ms" in text
    assert "兼容别名" in text

