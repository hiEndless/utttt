import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_release_ready_script_writes_structured_report() -> None:
    path = Path(PROJECT_ROOT) / "tools" / "local" / "check_release_ready.sh"
    text = path.read_text(encoding="utf-8")
    assert 'RELEASE_READY_REPORT_PATH="${RELEASE_READY_REPORT_PATH:-verification/reports/release_ready.latest.json}"' in text
    assert "schema_version\": \"release-ready-report-v1\"" in text
    assert "\"single_path_release_gate\"" in text
    assert "write_release_ready_report \"passed\"" in text
    assert "write_release_ready_report \"failed\"" in text
