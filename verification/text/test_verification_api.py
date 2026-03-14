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


def test_verification_api_summary_empty_branch_contains_memory_alert_fields(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    app = create_app(report_dir=str(reports))
    client = TestClient(app)

    resp = client.get("/internal/verification/reports/summary", params={"window_hours": 24})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("schema_version") == "verification-report-aggregate-v1"
    assert int(body.get("report_count") or 0) == 0
    assert int(body.get("memory_alert_code_count") or 0) == 0
    assert body.get("memory_top_alert_codes") == []


def test_verification_api_summary_schema_validation_enabled_passes(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    _write_report(reports / "quick-1.json", suite="quick", status="passed", finished_at_ms=1000, duration_ms=100)
    app = create_app(report_dir=str(reports), validate_summary_schema=True)
    client = TestClient(app)

    resp = client.get("/internal/verification/reports/summary", params={"window_hours": 24})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("schema_version") == "verification-report-aggregate-v1"


def test_verification_api_summary_schema_validation_enabled_fails_on_invalid_payload(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    _write_report(reports / "quick-1.json", suite="quick", status="passed", finished_at_ms=1000, duration_ms=100)

    import verification.api.app as app_mod

    monkeypatch.setattr(app_mod, "build_summary", lambda items: {"schema_version": "verification-report-aggregate-v1", "report_count": "bad"})  # noqa: ARG005
    app = create_app(report_dir=str(reports), validate_summary_schema=True)
    client = TestClient(app)

    resp = client.get("/internal/verification/reports/summary", params={"window_hours": 24})
    assert resp.status_code == 500
    assert resp.json().get("detail") == "verification_summary_schema_validation_failed"


def test_verification_api_execution_confidence_summary_empty(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    app = create_app(report_dir=str(reports))
    client = TestClient(app)

    resp = client.get("/internal/verification/reports/execution-confidence")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("schema_version") == "execution-confidence-summary-v1"
    assert int(body.get("report_count") or 0) == 0
    assert float(body.get("confidence_only_ratio") or 0.0) == 0.0
    assert body.get("trend") == []


def test_verification_api_execution_confidence_summary_with_trend(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    payload_latest = {
        "schema_version": "execution-confidence-metrics-v1",
        "ts_ms": 2000,
        "confidence_migration_metrics": {
            "decide_requests_total": 10,
            "confidence_only_requests": 2,
            "decision_confidence_requests": 8,
            "confidence_alias_mismatch_rejections": 1,
        },
    }
    payload_older = {
        "schema_version": "execution-confidence-metrics-v1",
        "ts_ms": 1000,
        "confidence_migration_metrics": {
            "decide_requests_total": 5,
            "confidence_only_requests": 1,
            "decision_confidence_requests": 4,
            "confidence_alias_mismatch_rejections": 0,
        },
    }
    (reports / "exec-conf-2.json").write_text(json.dumps(payload_latest, ensure_ascii=False), encoding="utf-8")
    (reports / "exec-conf-1.json").write_text(json.dumps(payload_older, ensure_ascii=False), encoding="utf-8")
    app = create_app(report_dir=str(reports))
    client = TestClient(app)

    resp = client.get("/internal/verification/reports/execution-confidence", params={"trend_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("schema_version") == "execution-confidence-summary-v1"
    assert int(body.get("report_count") or 0) == 2
    assert body.get("latest_report_id") == "exec-conf-2.json"
    assert int(body.get("latest_ts_ms") or 0) == 2000
    assert float(body.get("confidence_only_ratio") or 0.0) == 0.2
    trend = list(body.get("trend") or [])
    assert len(trend) == 2
    assert trend[0]["report_id"] == "exec-conf-2.json"
    assert float(trend[0]["confidence_only_ratio"]) == 0.2
