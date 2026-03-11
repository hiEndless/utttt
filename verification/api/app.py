from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Query

from verification.reports.aggregate_reports import build_summary

_ALLOWED_SCHEMA_VERSIONS = {"verification-report-v1", "verification-report-v2"}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _load_report(path: Path) -> Dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if str(data.get("schema_version") or "").strip() not in _ALLOWED_SCHEMA_VERSIONS:
        return None
    out = dict(data)
    out["report_id"] = path.name
    return out


def _list_reports(report_dir: Path) -> List[Dict[str, Any]]:
    if not report_dir.is_dir():
        return []
    items: List[Dict[str, Any]] = []
    for p in sorted(report_dir.glob("*.json")):
        item = _load_report(p)
        if item is None:
            continue
        items.append(item)
    items.sort(key=lambda x: _safe_int(x.get("finished_at_ms"), 0), reverse=True)
    return items


def create_app(*, report_dir: str = "verification/reports") -> FastAPI:
    app = FastAPI(title="verification_api", version="v1")
    report_root = Path(report_dir)

    @app.get("/internal/verification/healthz")
    async def healthz() -> Dict[str, Any]:
        return {
            "ok": True,
            "service": "verification_api",
            "report_dir": str(report_root),
        }

    @app.get("/internal/verification/reports/latest")
    async def latest_report(suite: str = Query(default="", description="suite name, optional")) -> Dict[str, Any]:
        items = _list_reports(report_root)
        suite_norm = str(suite or "").strip()
        if suite_norm:
            items = [x for x in items if str(x.get("suite") or "") == suite_norm]
        if not items:
            raise HTTPException(status_code=404, detail="verification_report_not_found")
        return items[0]

    @app.get("/internal/verification/reports")
    async def list_reports(
        suite: str = Query(default="", description="suite name, optional"),
        status: str = Query(default="", description="passed|failed, optional"),
        limit: int = Query(default=20, ge=1, le=1000),
    ) -> Dict[str, Any]:
        items = _list_reports(report_root)
        suite_norm = str(suite or "").strip()
        status_norm = str(status or "").strip()
        if suite_norm:
            items = [x for x in items if str(x.get("suite") or "") == suite_norm]
        if status_norm:
            if status_norm not in {"passed", "failed"}:
                raise HTTPException(status_code=400, detail="invalid_status_filter")
            items = [x for x in items if str(x.get("status") or "") == status_norm]
        out_items = items[: int(limit)]
        return {"items": out_items, "count": len(out_items)}

    @app.get("/internal/verification/reports/summary")
    async def summary(
        window_hours: int = Query(default=24, ge=1, le=24 * 365),
        suite: str = Query(default="", description="suite name, optional"),
    ) -> Dict[str, Any]:
        all_items = _list_reports(report_root)
        if not all_items:
            return {
                "schema_version": "verification-report-aggregate-v1",
                "report_count": 0,
                "passed": 0,
                "failed": 0,
                "pass_rate": 0.0,
                "avg_duration_ms": 0,
                "latest_finished_at_ms": 0,
                "suites": [],
            }

        latest_ms = max(_safe_int(x.get("finished_at_ms"), 0) for x in all_items)
        cutoff = latest_ms - int(window_hours) * 3600 * 1000

        items = [x for x in all_items if _safe_int(x.get("finished_at_ms"), 0) >= cutoff]
        suite_norm = str(suite or "").strip()
        if suite_norm:
            items = [x for x in items if str(x.get("suite") or "") == suite_norm]

        return build_summary(items)

    @app.get("/internal/verification/reports/{report_id}")
    async def get_report(report_id: str) -> Dict[str, Any]:
        name = str(report_id or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="report_id_required")
        if not name.endswith(".json"):
            name = f"{name}.json"
        path = report_root / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail="verification_report_not_found")
        data = _load_report(path)
        if data is None:
            raise HTTPException(status_code=404, detail="verification_report_not_found")
        return data

    return app
