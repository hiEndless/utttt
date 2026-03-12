from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any, Dict, List


def _load_reports(pattern: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for path in sorted(glob.glob(pattern)):
        p = Path(path)
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            schema_version = str(data.get("schema_version") or "").strip()
            if schema_version not in {
                "verification-report-v1",
                "verification-report-v2",
                "semantic-audit-v1",
                "symbol-memory-summary-run-v1",
            }:
                continue
            data["_path"] = str(p)
            out.append(data)
    return out


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def build_summary(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    verification_reports = [
        x for x in reports if str(x.get("schema_version") or "") in {"verification-report-v1", "verification-report-v2"}
    ]
    semantic_reports = [x for x in reports if str(x.get("schema_version") or "") == "semantic-audit-v1"]
    memory_summary_reports = [x for x in reports if str(x.get("schema_version") or "") == "symbol-memory-summary-run-v1"]

    total = len(verification_reports)
    passed = 0
    failed = 0
    duration_sum = 0
    latest_finished = 0
    by_suite: Dict[str, Dict[str, Any]] = {}

    for item in verification_reports:
        suite = str(item.get("suite") or "unknown")
        status = str(item.get("status") or "unknown")
        duration_ms = _to_int(item.get("duration_ms"), 0)
        finished_at_ms = _to_int(item.get("finished_at_ms"), 0)

        if status == "passed":
            passed += 1
        elif status == "failed":
            failed += 1

        duration_sum += max(0, duration_ms)
        latest_finished = max(latest_finished, finished_at_ms)

        slot = by_suite.setdefault(
            suite,
            {
                "suite": suite,
                "count": 0,
                "passed": 0,
                "failed": 0,
                "avg_duration_ms": 0,
                "latest_finished_at_ms": 0,
            },
        )
        slot["count"] += 1
        if status == "passed":
            slot["passed"] += 1
        elif status == "failed":
            slot["failed"] += 1
        slot["avg_duration_ms"] += max(0, duration_ms)
        slot["latest_finished_at_ms"] = max(_to_int(slot.get("latest_finished_at_ms"), 0), finished_at_ms)

    suites = []
    for suite in sorted(by_suite.keys()):
        item = dict(by_suite[suite])
        count = max(1, _to_int(item.get("count"), 1))
        item["avg_duration_ms"] = int(_to_int(item.get("avg_duration_ms"), 0) / count)
        suites.append(item)

    pass_rate = 0.0 if total <= 0 else round(float(passed) / float(total), 6)
    avg_duration = 0 if total <= 0 else int(duration_sum / total)

    semantic_error_count = 0
    semantic_warning_count = 0
    latest_semantic_report_path = ""
    if semantic_reports:
        latest_semantic = semantic_reports[-1]
        stats = latest_semantic.get("stats") if isinstance(latest_semantic.get("stats"), dict) else {}
        semantic_error_count = _to_int(stats.get("error_count"), 0)
        semantic_warning_count = _to_int(stats.get("warning_count"), 0)
        latest_semantic_report_path = str(latest_semantic.get("_path") or "")

    latest_memory_summary_report_path = ""
    memory_high_risk_symbols: List[Dict[str, Any]] = []
    memory_high_risk_symbol_count = 0
    memory_top_risk_score = 0.0
    if memory_summary_reports:
        latest_memory_summary = max(memory_summary_reports, key=lambda x: _to_int(x.get("ended_ms"), 0))
        latest_memory_summary_report_path = str(latest_memory_summary.get("_path") or "")
        memory_high_risk_symbols = [
            dict(x) for x in list(latest_memory_summary.get("high_risk_symbols") or []) if isinstance(x, dict)
        ]
        memory_high_risk_symbol_count = len(memory_high_risk_symbols)
        if memory_high_risk_symbols:
            memory_top_risk_score = max(
                [
                    float(item.get("risk_score") or 0.0)
                    for item in memory_high_risk_symbols
                    if isinstance(item, dict)
                ]
                or [0.0]
            )

    return {
        "schema_version": "verification-report-aggregate-v1",
        "verification_report_count": total,
        "report_count": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "avg_duration_ms": avg_duration,
        "latest_finished_at_ms": latest_finished,
        "suites": suites,
        "semantic_audit_count": len(semantic_reports),
        "semantic_error_count": semantic_error_count,
        "semantic_warning_count": semantic_warning_count,
        "latest_semantic_report_path": latest_semantic_report_path,
        "memory_summary_run_count": len(memory_summary_reports),
        "latest_memory_summary_report_path": latest_memory_summary_report_path,
        "memory_high_risk_symbol_count": memory_high_risk_symbol_count,
        "memory_top_risk_score": round(float(memory_top_risk_score), 6),
        "memory_high_risk_symbols": memory_high_risk_symbols,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="聚合 verification 报告")
    p.add_argument("--glob", default="verification/reports/*.json", help="报告文件 glob")
    p.add_argument("--output", default="", help="可选：写入输出文件")
    p.add_argument("--compact", action="store_true", help="紧凑 JSON 输出")
    return p


def main(argv: List[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    reports = _load_reports(str(args.glob))
    summary = build_summary(reports)
    rendered = json.dumps(summary, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2)
    print(rendered)

    output = str(args.output or "").strip()
    if output:
        p = Path(output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
