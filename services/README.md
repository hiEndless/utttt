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
