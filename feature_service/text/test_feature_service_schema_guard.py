import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.feature_service.src.contracts import FeatureResponse, RawStructureResponse


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_raw_structure_schema_is_frozen():
    schema_file = Path(PROJECT_ROOT) / "feature_service/docs/schemas/raw_structure_response.schema.json"
    frozen = _load_json(schema_file)
    current = RawStructureResponse.model_json_schema()
    assert current == frozen


def test_feature_response_schema_is_frozen():
    schema_file = Path(PROJECT_ROOT) / "feature_service/docs/schemas/feature_response.schema.json"
    frozen = _load_json(schema_file)
    current = FeatureResponse.model_json_schema()
    assert current == frozen
