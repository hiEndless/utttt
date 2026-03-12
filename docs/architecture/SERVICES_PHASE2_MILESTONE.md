# Services Phase-2 Milestone

更新时间：2026-03-12
状态：in_progress (feature_service fully migrated, no legacy wrappers)

## 1. 目标

在不破坏现有运行链路的前提下，将服务启动入口逐步收敛到 `services/*`，并把旧入口改为兼容壳。

## 2. 已完成试点

1. `feature_service/main.py`
- migrated impl: `services/feature_service/runtime/main.py`
- legacy wrapper status: removed after batch-c

2. `market_state_engine/main.py`
- migrated impl: `services/market_state_engine/runtime/main.py`
- legacy wrapper kept: `market_state_engine/main.py`

2.1 `market_state_engine/{app,routes,contracts}.py`
- migrated impl: `services/market_state_engine/src/{app,routes,contracts}.py`
- legacy wrapper kept: `market_state_engine/{app,routes,contracts}.py`

2.2 `market_state_engine/service.py`
- migrated impl: `services/market_state_engine/src/service.py`
- legacy wrapper kept: `market_state_engine/service.py`（模块桥接兼容）

3. `execution_service/main.py`
- migrated impl: `services/execution_service/runtime/main.py`
- legacy wrapper kept: `execution_service/main.py`

4. `event_center_new/main.py`
- migrated impl: `services/event_center_new/runtime/main.py`
- legacy wrapper kept: `event_center_new/main.py`

5. `event_center_new/replay_main.py`
- migrated impl: `services/event_center_new/runtime/replay_main.py`
- legacy wrapper kept: `event_center_new/replay_main.py`

6. `agent_server_new/runner.py`
- migrated impl: `services/agent_server_new/runtime/runner.py`
- legacy wrapper kept: `agent_server_new/runner.py`

7. `agent_server_new/pipeline_smoke.py`
- migrated impl: `services/agent_server_new/runtime/pipeline_smoke.py`
- legacy wrapper kept: `agent_server_new/pipeline_smoke.py`

8. `agent_server_new/memory_summary_runner.py`
- migrated impl: `services/agent_server_new/runtime/memory_summary_runner.py`
- legacy wrapper kept: `agent_server_new/memory_summary_runner.py`

9. `feature_service/app.py`
- migrated impl: `services/feature_service/src/app.py`
- legacy wrapper status: removed in batch A

10. `feature_service/routes.py`
- migrated impl: `services/feature_service/src/routes.py`
- legacy wrapper status: removed in batch A

11. `feature_service/service.py`
- migrated impl: `services/feature_service/src/service.py`
- legacy wrapper status: removed in batch A

12. `feature_service/contracts.py`
- migrated impl: `services/feature_service/src/contracts.py`
- legacy wrapper status: removed in batch A

13. `feature_service/providers/{bundle,noop,degradation_state}.py`
- migrated impl: `services/feature_service/src/providers/{bundle,noop,degradation_state}.py`
- legacy wrapper status: removed in batch B

14. `feature_service/providers/fallback_structure_providers.py`
- migrated impl: `services/feature_service/src/providers/fallback_structure_providers.py`
- legacy wrapper status: removed in batch B

15. `feature_service/providers/{static,migrated}_structure_providers.py`
- migrated impl: `services/feature_service/src/providers/{static,migrated}_structure_providers.py`
- legacy wrapper status: removed in batch B

16. `feature_service/providers/{indicators_provider,future_source_providers,__init__}.py`
- migrated impl: `services/feature_service/src/providers/{indicators_provider,future_source_providers,__init__}.py`
- legacy wrapper status: removed in batch B

17. `feature_service/normalizers/{response_normalizer,__init__}.py`
- migrated impl: `services/feature_service/src/normalizers/{response_normalizer,__init__}.py`
- legacy wrapper status: removed in batch A

18. `feature_service/ports/*.py`
- migrated impl: `services/feature_service/src/ports/*.py`
- legacy wrapper status: removed in batch A

19. `feature_service/providers/market_structure_migrated/`
- migrated impl: `services/feature_service/src/providers/market_structure_migrated/`
- legacy wrapper status: removed in batch C

## 3. 保障机制

- 结构检查：`bash tools/local/check_structure.sh`
- services_map 一致性检查：`bash tools/local/check_services_map_consistency.sh`
- 快速回归：`bash tools/ci/verify_quick.sh`

## 4. 当前风险

1. 旧入口兼容壳仍然较多，尚未进入清理窗口。
2. 部分测试依赖 monkeypatch 旧入口模块符号，迁移需保持桥接兼容。
3. workflow/snapshot/text-wiring 仍有 `scripts/*` 硬绑定。

## 5. 下一阶段建议

1. 进入 Phase-2.5：补齐其余可迁移入口（非主 main，但常用 CLI）。
2. 启动 Phase-3 前置：明确 `scripts/*` 兼容下线顺序与每批回滚方案。
3. 将服务真实业务代码按模块批次迁入 `services/<svc>/src`（非仅入口迁移）。
4. `feature_service` 已进入“core src migrated + compat wrapper”状态，可开始设计兼容壳下线窗口。
5. 兼容壳下线草案已落地：`docs/operations/FEATURE_SERVICE_COMPAT_WRAPPER_DECOMMISSION.md`。
6. 已完成 Batch A：删除 `app/routes/service/contracts` 与 `ports/normalizers` 兼容壳。
7. 已完成 Batch B：删除 `feature_service/providers/*.py` 顶层兼容壳（保留 `market_structure_migrated/` 目录到 Batch C）。
8. 已完成 Batch C：删除 `feature_service/providers/market_structure_migrated/` 兼容目录。
9. 已移除 `feature_service/main.py` 兼容入口，`feature_service` 进入 fully-migrated 状态。
10. 已启动 `market_state_engine` Batch A：`app/routes/contracts` 已迁入 `services/market_state_engine/src/`。
11. 已执行 `market_state_engine` Batch B（阶段1）：`service.py` 已迁入 `services/market_state_engine/src/`，旧路径保留桥接。
