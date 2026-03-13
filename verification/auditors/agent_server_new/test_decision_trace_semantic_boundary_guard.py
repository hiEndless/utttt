import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_decision_trace_pipeline_mode_frozen_to_minimal() -> None:
    schema_path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "docs" / "decision_trace.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    routing = dict((schema.get("properties") or {}).get("routing") or {})
    routing_props = dict(routing.get("properties") or {})
    pipeline_mode = dict(routing_props.get("pipeline_mode") or {})
    assert list(pipeline_mode.get("enum") or []) == ["minimal"]


def test_decision_trace_semantic_boundary_doc_guard() -> None:
    contract_doc = (Path(PROJECT_ROOT) / "services" / "agent_server_new" / "docs" / "runner_output_contract.md").read_text(
        encoding="utf-8"
    )
    assert "语义快照字段" in contract_doc
    assert "语义建议字段" in contract_doc
    assert "sizing" in contract_doc
    assert "allowance" in contract_doc
    assert "execution_service" in contract_doc
    assert "唯一权威" in contract_doc
