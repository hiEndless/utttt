from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "contracts/registry.yaml"
INDEX_PATH = ROOT / "contracts/mappings/index.yaml"


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _render_yaml(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, allow_unicode=False, sort_keys=False)


def build_index(registry: dict[str, Any]) -> dict[str, Any]:
    entries = registry.get("entries", [])
    mappings: list[dict[str, str]] = []
    for entry in entries:
        if entry.get("kind") != "mapping":
            continue
        source = str(entry.get("source", "")).strip()
        if not source:
            continue
        mappings.append(
            {
                "id": str(entry.get("id", "")).strip(),
                "source": source,
                "owner": str(entry.get("owner", "")).strip(),
                "status": "active",
            }
        )

    updated = str(registry.get("updated_at") or dt.date.today().isoformat())
    return {
        "version": 1,
        "updated_at": updated,
        "source_of_truth": "contracts/registry.yaml",
        "mappings": mappings,
        "note": "Auto-generated from registry kind=mapping entries.",
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Sync contracts/mappings/index.yaml from contracts/registry.yaml")
    p.add_argument("--write", action="store_true", help="write generated index to contracts/mappings/index.yaml")
    args = p.parse_args()

    registry = _load_yaml(REGISTRY_PATH)
    generated = build_index(registry)
    rendered = _render_yaml(generated)

    if args.write:
        INDEX_PATH.write_text(rendered, encoding="utf-8")
        print(f"[ok] wrote {INDEX_PATH}")
        return 0

    if not INDEX_PATH.exists():
        print(f"[failed] missing {INDEX_PATH}")
        return 1

    current = INDEX_PATH.read_text(encoding="utf-8")
    if current != rendered:
        print("[failed] contracts/mappings/index.yaml drift detected")
        print("run: python3 contracts/mappings/sync_index_from_registry.py --write")
        return 1

    print("[ok] contracts/mappings/index.yaml is in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
