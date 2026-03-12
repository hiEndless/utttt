# market_state_engine (migration placeholder)

Runtime source path: `market_state_engine/`
Target canonical path: `services/market_state_engine/`

Notes:
- Keep imports/runtime on legacy path during compatibility window.
- `main.py` runtime implementation has moved to `services/market_state_engine/runtime/main.py`.
- Batch A migrated implementations:
  - `services/market_state_engine/src/app.py`
  - `services/market_state_engine/src/routes.py`
  - `services/market_state_engine/src/contracts.py`
- Batch B (phase-1) migrated implementation:
  - `services/market_state_engine/src/service.py`
- Batch B (phase-2) migrated implementation:
  - `services/market_state_engine/src/errors.py`
- Batch B (phase-3) migrated implementation:
  - `services/market_state_engine/src/engine.py`
- Batch B (phase-4) migrated implementation:
  - `services/market_state_engine/src/msl.py`
- Batch B (phase-5) migrated implementation:
  - `services/market_state_engine/src/adapters/in_memory_feature_store.py`
  - `services/market_state_engine/src/adapters/raw_structure_http.py`
- Batch B (phase-6) migrated implementation:
  - `services/market_state_engine/src/adapters/selected_events_redis.py`
- Batch B (phase-7) migrated implementation:
  - `services/market_state_engine/src/ports/__init__.py`
  - `services/market_state_engine/src/ports/raw_structure_provider.py`
  - `services/market_state_engine/src/ports/selected_event_provider.py`
  - `services/market_state_engine/src/ports/storage/__init__.py`
  - `services/market_state_engine/src/ports/storage/feature_store.py`
- Batch C (phase-1) migrated implementation:
  - `services/market_state_engine/src/factors/`
  - `services/market_state_engine/src/state_inference/`
  - `services/market_state_engine/src/config/state_inference_profiles.json`
- Batch C (phase-2) compatibility convergence:
  - `market_state_engine/factors/` switched to wrappers
  - `market_state_engine/state_inference/` switched to wrappers
- Batch C (phase-3) compatibility convergence:
  - `market_state_engine/__init__.py` switched to wrapper
  - `market_state_engine/adapters/__init__.py` switched to wrapper
- Decommission plan:
  - `docs/operations/MARKET_STATE_ENGINE_COMPAT_WRAPPER_DECOMMISSION.md`
