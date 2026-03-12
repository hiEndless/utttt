# Services Layer

This directory is the canonical business-service layer target.

Current migration mode:
- Keep runtime service source in existing root directories for compatibility.
- Use `services/services_map.yaml` as the single migration map.
- Migrate service code physically in later phases once import/runtime paths are switched.

Current scaffold:
- `services/feature_service/`
- `services/market_state_engine/`
- `services/event_center_new/`
- `services/agent_server_new/`
- `services/execution_service/`

Soft migration entrypoints (phase-1 runtime unification):
- `python -m services.feature_service.main`
- `python -m services.market_state_engine.main`
- `python -m services.event_center_new.main`
- `python -m services.event_center_new.replay_main`
- `python -m services.agent_server_new.main`
- `python -m services.agent_server_new.pipeline_smoke`
- `python -m services.agent_server_new.memory_summary_runner`
- `python -m services.execution_service.main`

Recommended local wrappers:
- `bash tools/local/run_feature_service.sh`
- `bash tools/local/run_market_state_engine.sh`
- `bash tools/local/run_event_center.sh`
- `bash tools/local/run_event_center_replay.sh`
- `bash tools/local/run_agent_runner.sh`
- `bash tools/local/run_agent_pipeline_smoke.sh`
- `bash tools/local/run_agent_memory_summary.sh`
- `bash tools/local/run_execution_service.sh`

Pilot migration note:
- `feature_service` legacy wrappers are fully removed.
- runtime entrypoint is `services/feature_service/runtime/main.py`.
- `market_state_engine/main.py` is now a legacy wrapper.
- runtime implementation moved to `services/market_state_engine/runtime/main.py`.
- `execution_service/main.py` is now a legacy wrapper.
- runtime implementation moved to `services/execution_service/runtime/main.py`.
- `event_center_new/main.py` is now a legacy wrapper.
- runtime implementation moved to `services/event_center_new/runtime/main.py`.
- `event_center_new/replay_main.py` is now a legacy wrapper.
- runtime implementation moved to `services/event_center_new/runtime/replay_main.py`.
- `agent_server_new/runner.py` is now a legacy wrapper.
- runtime implementation moved to `services/agent_server_new/runtime/runner.py`.
- `agent_server_new/pipeline_smoke.py` is now a legacy wrapper.
- runtime implementation moved to `services/agent_server_new/runtime/pipeline_smoke.py`.
- `agent_server_new/memory_summary_runner.py` is now a legacy wrapper.
- runtime implementation moved to `services/agent_server_new/runtime/memory_summary_runner.py`.
