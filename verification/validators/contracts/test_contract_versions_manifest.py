from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.execution_service.version import SCHEMA_MAPPING_VERSION
from services.feature_service.src.version import FEATURE_RESPONSE_SCHEMA_VERSION
from services.market_state_engine.src.version import MSL_SCHEMA_VERSION


def _read_manifest_value(text: str, *, name: str) -> str:
    pattern = re.compile(rf"- name:\s*{re.escape(name)}\s*\n\s*value:\s*\"([^\"]+)\"", re.MULTILINE)
    m = pattern.search(text)
    assert m is not None, f"manifest missing version entry: {name}"
    return str(m.group(1))


def _read_manifest_source(text: str, *, name: str) -> str:
    pattern = re.compile(
        rf"- name:\s*{re.escape(name)}\s*\n\s*value:\s*\"[^\"]+\"\s*\n\s*source:\s*\"([^\"]+)\"",
        re.MULTILINE,
    )
    m = pattern.search(text)
    assert m is not None, f"manifest missing source entry: {name}"
    return str(m.group(1))


def test_contract_versions_manifest_aligned() -> None:
    manifest = PROJECT_ROOT / "contracts" / "versions" / "manifest.yaml"
    text = manifest.read_text(encoding="utf-8")

    assert _read_manifest_value(text, name="execution_schema_mapping_version") == SCHEMA_MAPPING_VERSION
    assert _read_manifest_value(text, name="feature_response_schema_version") == FEATURE_RESPONSE_SCHEMA_VERSION
    assert _read_manifest_value(text, name="market_state_msl_schema_version") == str(MSL_SCHEMA_VERSION)


def test_contract_versions_manifest_sources_exist() -> None:
    manifest = PROJECT_ROOT / "contracts" / "versions" / "manifest.yaml"
    text = manifest.read_text(encoding="utf-8")
    for name in (
        "execution_schema_mapping_version",
        "feature_response_schema_version",
        "market_state_msl_schema_version",
    ):
        source_rel = _read_manifest_source(text, name=name)
        assert (PROJECT_ROOT / source_rel).is_file(), f"manifest source not found: {source_rel}"

