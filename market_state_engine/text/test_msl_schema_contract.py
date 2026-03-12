from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.market_state_engine.src.errors import FeatureDataUnavailableFromUpstreamError
from services.market_state_engine.src.service import MarketStateService


def _load_schema() -> Dict[str, Any]:
    path = Path(PROJECT_ROOT) / "market_state_engine" / "docs" / "msl.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(value: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    errors: List[str] = []
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            return [f"{path}: expected object"]
        props = dict(schema.get("properties") or {})
        required = [str(x) for x in list(schema.get("required") or [])]
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required '{key}'")
        if schema.get("additionalProperties") is False:
            extras = [k for k in value.keys() if k not in props]
            if extras:
                errors.append(f"{path}: unexpected keys {sorted(extras)}")
        for key, child_schema in props.items():
            if key in value and isinstance(child_schema, dict):
                errors.extend(_validate(value[key], child_schema, f"{path}.{key}"))
        return errors
    if expected_type == "array":
        if not isinstance(value, list):
            return [f"{path}: expected array"]
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                errors.extend(_validate(item, item_schema, f"{path}[{idx}]"))
        return errors
    if expected_type == "string":
        if not isinstance(value, str):
            return [f"{path}: expected string"]
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            errors.append(f"{path}: minLength={min_length}")
        enum = schema.get("enum")
        if isinstance(enum, list) and value not in enum:
            errors.append(f"{path}: value '{value}' not in enum")
        return errors
    if expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return [f"{path}: expected integer"]
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{path}: minimum={minimum}")
        if isinstance(maximum, (int, float)) and value > maximum:
            errors.append(f"{path}: maximum={maximum}")
        return errors
    if expected_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return [f"{path}: expected number"]
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        numeric = float(value)
        if isinstance(minimum, (int, float)) and numeric < minimum:
            errors.append(f"{path}: minimum={minimum}")
        if isinstance(maximum, (int, float)) and numeric > maximum:
            errors.append(f"{path}: maximum={maximum}")
        return errors
    return errors


class _OkRawProvider:
    async def get_raw_structure(self, exchange: str, symbol: str):
        return {
            "symbol": symbol,
            "horizons": {},
            "orderbook": {},
            "open_interest": {},
            "behavioral": {},
            "pre_decision_structure": {},
        }


class _UnavailableRawProvider:
    async def get_raw_structure(self, exchange: str, symbol: str):
        raise FeatureDataUnavailableFromUpstreamError(
            exchange=exchange,
            symbol=symbol,
            degraded_reasons=["feature_data_unavailable"],
        )


def test_msl_schema_surface() -> None:
    schema = _load_schema()
    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is False
    required = set(schema.get("required") or [])
    props = set((schema.get("properties") or {}).keys())
    assert required == props


def test_msl_schema_validates_ok_branch() -> None:
    async def _run():
        service = MarketStateService(raw_structure_provider=_OkRawProvider())
        out = await service.get_market_state("binance", "ETHUSDT")
        schema = _load_schema()
        errors = _validate(dict(out.get("msl") or {}), schema)
        assert errors == []

    asyncio.run(_run())


def test_msl_schema_validates_data_unavailable_branch() -> None:
    async def _run():
        service = MarketStateService(raw_structure_provider=_UnavailableRawProvider())
        out = await service.get_market_state("binance", "ETHUSDT")
        schema = _load_schema()
        errors = _validate(dict(out.get("msl") or {}), schema)
        assert errors == []

    asyncio.run(_run())
