from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _diff(a: Any, b: Any, prefix: str = "$") -> List[str]:
    out: List[str] = []
    if type(a) is not type(b):
        out.append(f"{prefix}: type mismatch ({type(a).__name__} != {type(b).__name__})")
        return out
    if isinstance(a, dict):
        ka, kb = set(a.keys()), set(b.keys())
        for k in sorted(ka - kb):
            out.append(f"{prefix}.{k}: only_in_a")
        for k in sorted(kb - ka):
            out.append(f"{prefix}.{k}: only_in_b")
        for k in sorted(ka & kb):
            out.extend(_diff(a[k], b[k], f"{prefix}.{k}"))
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{prefix}: list length mismatch ({len(a)} != {len(b)})")
            return out
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(_diff(x, y, f"{prefix}[{i}]"))
        return out
    if a != b:
        out.append(f"{prefix}: value mismatch ({a!r} != {b!r})")
    return out


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="JSON deep diff")
    p.add_argument("--left", required=True)
    p.add_argument("--right", required=True)
    p.add_argument("--output", default="")
    args = p.parse_args(argv)

    left = _load(args.left)
    right = _load(args.right)
    diffs = _diff(left, right)

    payload: Dict[str, Any] = {
        "schema_version": "json-diff-v1",
        "left": str(args.left),
        "right": str(args.right),
        "diff_count": len(diffs),
        "diffs": diffs,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)

    out = str(args.output or "").strip()
    if out:
        Path(out).write_text(rendered + "\n", encoding="utf-8")

    return 0 if not diffs else 1


if __name__ == "__main__":
    raise SystemExit(main())
