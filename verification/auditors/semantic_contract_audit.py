from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "contracts/registry.yaml"
POLICY_PATH = ROOT / "contracts/semantic_policies/field_semantics.yaml"
DEFAULT_OUT = ROOT / "verification/reports/semantic_audit.latest.json"


class AuditError(RuntimeError):
    pass


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_props(node: Any, pointer: str = "#"):
    if not isinstance(node, dict):
        return

    props = node.get("properties")
    if isinstance(props, dict):
        for key, child in props.items():
            child_ptr = f"{pointer}/properties/{key}"
            yield key, child_ptr, child
            yield from _iter_props(child, child_ptr)

    items = node.get("items")
    if isinstance(items, dict):
        yield from _iter_props(items, f"{pointer}/items")

    for bag in ("$defs", "definitions"):
        defs = node.get(bag)
        if isinstance(defs, dict):
            for key, child in defs.items():
                yield from _iter_props(child, f"{pointer}/{bag}/{key}")


def _shape_signature(node: dict[str, Any]) -> str:
    t = node.get("type")
    if isinstance(t, list):
        t = "|".join(sorted(str(x) for x in t))
    if t == "array":
        items = node.get("items")
        if isinstance(items, dict):
            item_t = items.get("type", "any")
            return f"array[{item_t}]"
        return "array[any]"
    if "enum" in node and isinstance(node["enum"], list):
        return f"enum[{len(node['enum'])}]"
    if isinstance(t, str):
        return t
    return "unknown"


def run_audit() -> dict[str, Any]:
    registry = _load_yaml(REGISTRY_PATH)
    policy = _load_yaml(POLICY_PATH)

    schema_entries = [e for e in registry.get("entries", []) if e.get("kind") == "schema"]
    occurrences: dict[str, list[dict[str, Any]]] = {}
    errors: list[str] = []
    warnings: list[str] = []

    for entry in schema_entries:
        source = str(entry.get("source", "")).strip()
        if not source:
            continue
        path = ROOT / source
        if not path.exists():
            errors.append(f"missing schema source: {source}")
            continue
        try:
            schema = _load_json(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"invalid schema json: {source}: {exc}")
            continue

        for name, ptr, node in _iter_props(schema):
            if not isinstance(node, dict):
                continue
            item = {
                "entry_id": entry.get("id", ""),
                "source": source,
                "location": f"{source}{ptr}",
                "shape": _shape_signature(node),
            }
            occurrences.setdefault(name, []).append(item)

    fields = policy.get("fields", [])
    for field in fields:
        name = str(field.get("name", "")).strip()
        if not name:
            continue
        occ = occurrences.get(name, [])

        expected_shape = str(field.get("expected_shape", "")).strip()
        if expected_shape:
            ok = False
            for x in occ:
                shape = x["shape"]
                if expected_shape == "array[string]" and shape == "array[string]":
                    ok = True
                    break
                if expected_shape == "enum" and shape.startswith("enum["):
                    ok = True
                    break
                if expected_shape == "integer" and shape == "integer":
                    ok = True
                    break
            if not ok and occ:
                warnings.append(f"field {name}: expected_shape={expected_shape} not observed")

        allowed_locations = field.get("allowed_locations") or []
        if allowed_locations:
            allowed = set(str(x) for x in allowed_locations)
            for x in occ:
                if x["location"] not in allowed:
                    errors.append(
                        f"field {name}: disallowed location {x['location']} (allowed={sorted(allowed)})"
                    )

        # type drift on same field name
        shapes = sorted({x["shape"] for x in occ})
        if len(shapes) > 1:
            warnings.append(f"field {name}: multiple shapes detected {shapes}")

    report = {
        "schema_version": "semantic-audit-v1",
        "registry": str(REGISTRY_PATH.relative_to(ROOT)),
        "policy": str(POLICY_PATH.relative_to(ROOT)),
        "stats": {
            "schema_entries": len(schema_entries),
            "tracked_fields": len(fields),
            "observed_field_names": len(occurrences),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
        "errors": errors,
        "warnings": warnings,
    }
    return report


def main() -> int:
    p = argparse.ArgumentParser(description="Semantic contract auditor")
    p.add_argument("--output", default=str(DEFAULT_OUT), help="json report output path")
    p.add_argument("--strict", action="store_true", help="exit non-zero when warnings exist")
    args = p.parse_args()

    report = run_audit()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report["stats"], ensure_ascii=False))

    if report["stats"]["error_count"] > 0:
        return 1
    if args.strict and report["stats"]["warning_count"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
