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
