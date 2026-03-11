# feature_service (migration placeholder)

Runtime source path: `feature_service/`
Target canonical path: `services/feature_service/`

Notes:
- Keep imports/runtime on legacy path during compatibility window.
- `main.py` runtime implementation has moved to `services/feature_service/runtime/main.py`.
- `app.py` implementation has moved to `services/feature_service/src/app.py`.
- `routes.py` implementation has moved to `services/feature_service/src/routes.py`.
- `service.py` implementation has moved to `services/feature_service/src/service.py`.
- `contracts.py` implementation has moved to `services/feature_service/src/contracts.py`.
- provider基础实现已迁入 `services/feature_service/src/providers/`：`bundle.py`、`noop.py`、`degradation_state.py`。
