from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def _load_json(path: str) -> Dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return dict(data) if isinstance(data, dict) else {}


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="检查 verification 聚合报告阈值")
    p.add_argument("--summary", default="verification/reports/summary.latest.json", help="聚合报告路径")
    p.add_argument("--min-pass-rate", type=float, default=1.0, help="最低通过率")
    p.add_argument("--max-failed", type=int, default=0, help="最大失败报告数")
    p.add_argument("--min-reports", type=int, default=1, help="最小报告数")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    summary = _load_json(str(args.summary))

    report_count = _to_int(summary.get("report_count"), 0)
    failed = _to_int(summary.get("failed"), 0)
    pass_rate = _to_float(summary.get("pass_rate"), 0.0)

    errors = []
    if report_count < int(args.min_reports):
        errors.append(f"report_count<{int(args.min_reports)} (actual={report_count})")
    if failed > int(args.max_failed):
        errors.append(f"failed>{int(args.max_failed)} (actual={failed})")
    if pass_rate < float(args.min_pass_rate):
        errors.append(f"pass_rate<{float(args.min_pass_rate)} (actual={pass_rate})")

    if errors:
        print("[failed] verification thresholds not satisfied")
        for item in errors:
            print(f"- {item}")
        return 1

    print("[passed] verification thresholds satisfied")
    print(f"report_count={report_count} failed={failed} pass_rate={pass_rate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
