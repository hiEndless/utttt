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
- provider基础实现已迁入 `services/feature_service/src/providers/`：`bundle.py`、`noop.py`、`degradation_state.py`、`fallback_structure_providers.py`、`static_structure_providers.py`、`migrated_structure_providers.py`、`indicators_provider.py`、`future_source_providers.py`、`__init__.py`。
- `market_structure_migrated/` 已镜像迁入 `services/feature_service/src/providers/market_structure_migrated/`，旧目录保留为兼容回滚副本。
- 旧 `feature_service/providers/market_structure_migrated/**/*.py` 已基本收敛为兼容壳（少量测试猴子补丁相关文件保留旧路径实现）。
- normalizer实现已迁入 `services/feature_service/src/normalizers/`：`response_normalizer.py`、`__init__.py`。
- ports接口定义已迁入 `services/feature_service/src/ports/`：`__init__.py` 与各 provider protocol 文件。
