from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from verification.api.app import create_app


def _write_report(path: Path, *, suite: str, status: str, finished_at_ms: int, duration_ms: int) -> None:
    payload = {
        "schema_version": "verification-report-v2",
        "suite": suite,
        "git_sha": "abc123",
        "env": "test",
        "suite_tags": ["unit"],
        "status": status,
        "exit_code": 0 if status == "passed" else 1,
        "started_at_ms": max(1, int(finished_at_ms - duration_ms)),
        "finished_at_ms": int(finished_at_ms),
        "duration_ms": int(duration_ms),
        "guards": [{"name": "quick", "status": status, "duration_ms": int(duration_ms)}],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_verification_api_read_only_endpoints(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    _write_report(reports / "quick-1.json", suite="quick", status="passed", finished_at_ms=1000, duration_ms=100)
    _write_report(reports / "quick-2.json", suite="quick", status="failed", finished_at_ms=2000, duration_ms=200)
    _write_report(reports / "full-1.json", suite="new_arch_full", status="passed", finished_at_ms=3000, duration_ms=300)
    (reports / "verification_report_v2.schema.json").write_text("{}", encoding="utf-8")

    app = create_app(report_dir=str(reports))
    client = TestClient(app)

    r_health = client.get("/internal/verification/healthz")
    assert r_health.status_code == 200
    assert r_health.json().get("ok") is True

    r_latest = client.get("/internal/verification/reports/latest", params={"suite": "quick"})
    assert r_latest.status_code == 200
    assert r_latest.json().get("suite") == "quick"
    assert int(r_latest.json().get("finished_at_ms") or 0) == 2000

    r_list = client.get("/internal/verification/reports", params={"suite": "quick", "status": "passed", "limit": 10})
    assert r_list.status_code == 200
    body_list = r_list.json()
    assert int(body_list.get("count") or 0) == 1
    assert body_list["items"][0]["status"] == "passed"

    r_summary = client.get("/internal/verification/reports/summary", params={"window_hours": 24})
    assert r_summary.status_code == 200
    body_summary = r_summary.json()
    assert body_summary.get("schema_version") == "verification-report-aggregate-v1"
    assert int(body_summary.get("report_count") or 0) == 3

    r_get = client.get("/internal/verification/reports/full-1")
    assert r_get.status_code == 200
    assert r_get.json().get("suite") == "new_arch_full"

    r_missing = client.get("/internal/verification/reports/missing")
    assert r_missing.status_code == 404
