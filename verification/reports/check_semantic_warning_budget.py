from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


FIELD_RE = re.compile(r"field\s+([a-zA-Z0-9_]+):")


def _load_json(path: str) -> dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return dict(data) if isinstance(data, dict) else {}


def _load_yaml(path: str) -> dict[str, Any]:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return dict(data) if isinstance(data, dict) else {}


def _extract_field(msg: str) -> str:
    m = FIELD_RE.search(msg or "")
    return m.group(1) if m else "_unknown"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Check semantic warning budget by field")
    p.add_argument("--audit", default="verification/reports/semantic_audit.latest.json", help="semantic audit report")
    p.add_argument("--budget", default="verification/reports/semantic_warning_budget.yaml", help="warning budget yaml")
    args = p.parse_args(argv)

    audit = _load_json(str(args.audit))
    budget = _load_yaml(str(args.budget))

    warnings = audit.get("warnings") if isinstance(audit.get("warnings"), list) else []
    default_max = int(budget.get("default_max", 0))
    field_budget = budget.get("fields") if isinstance(budget.get("fields"), dict) else {}

    counts: dict[str, int] = {}
    for w in warnings:
        field = _extract_field(str(w))
        counts[field] = counts.get(field, 0) + 1

    errors: list[str] = []
    for field, count in sorted(counts.items()):
        max_allowed = int(field_budget.get(field, default_max))
        if count > max_allowed:
            errors.append(f"field={field} warnings={count} > budget={max_allowed}")

    if errors:
        print("[failed] semantic warning budget exceeded")
        for e in errors:
            print(f"- {e}")
        return 1

    print("[passed] semantic warning budget satisfied")
    print(json.dumps({"counts": counts, "default_max": default_max}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
