# Services Phase-2 Milestone

更新时间：2026-03-12
状态：completed (all five services fully migrated, no legacy wrappers)

## 1. 目标

在不破坏现有运行链路的前提下，将服务启动入口逐步收敛到 `services/*`，并把旧入口改为兼容壳。

## 2. 已完成试点

1. `feature_service/main.py`
- migrated impl: `services/feature_service/runtime/main.py`
- legacy wrapper status: removed after batch-c

2. `market_state_engine/main.py`
- migrated impl: `services/market_state_engine/runtime/main.py`
- legacy wrapper status: removed in 2.16 (batch-d phase-1)

2.1 `market_state_engine/{app,routes,contracts}.py`
- migrated impl: `services/market_state_engine/src/{app,routes,contracts}.py`
- legacy wrapper status: removed in 2.13 (batch-a phase-1)

2.2 `market_state_engine/service.py`
- migrated impl: `services/market_state_engine/src/service.py`
- legacy wrapper status: removed in 2.16 (batch-d phase-1)

2.3 `market_state_engine/errors.py`
- migrated impl: `services/market_state_engine/src/errors.py`
- legacy wrapper status: removed in 2.13 (batch-a phase-1)

2.4 `market_state_engine/engine.py`
- migrated impl: `services/market_state_engine/src/engine.py`
- legacy wrapper status: removed in 2.16 (batch-d phase-1)

2.5 `market_state_engine/msl.py`
- migrated impl: `services/market_state_engine/src/msl.py`
- legacy wrapper status: removed in 2.13 (batch-a phase-1)

2.6 `market_state_engine/adapters/{in_memory_feature_store,raw_structure_http}.py`
- migrated impl: `services/market_state_engine/src/adapters/{in_memory_feature_store,raw_structure_http}.py`
- legacy wrapper status: removed in 2.14 (batch-b phase-1)

2.7 `market_state_engine/adapters/selected_events_redis.py`
- migrated impl: `services/market_state_engine/src/adapters/selected_events_redis.py`
- legacy wrapper status: removed in 2.14 (batch-b phase-1)

2.8 `market_state_engine/ports/**`
- migrated impl: `services/market_state_engine/src/ports/**`
- legacy wrapper status: removed in 2.14 (batch-b phase-1)

2.9 `market_state_engine/{factors,state_inference}/**`
- migrated impl: `services/market_state_engine/src/{factors,state_inference}/**`
- legacy wrapper status: removed in 2.15 (batch-c phase-1)

2.10 `market_state_engine/{factors,state_inference}/**` wrappers
- migrated impl: `services/market_state_engine/src/{factors,state_inference}/**`
- legacy wrapper status: removed in 2.15 (batch-c phase-1)

2.11 `market_state_engine/{__init__.py,adapters/__init__.py}`
- migrated impl: `services/market_state_engine/src/{__init__.py,adapters/__init__.py}`
- legacy wrapper status:
  - `market_state_engine/__init__.py` removed in 2.16 (batch-d phase-1)
  - `market_state_engine/adapters/__init__.py` removed in 2.14 (batch-b phase-1)

2.12 `market_state_engine` decommission batch-0
- 内部调用方迁移至 `services.market_state_engine.src.*`
- 新增守卫：`tools/local/check_market_state_legacy_imports.sh`

2.13 `market_state_engine` decommission batch-a (phase-1)
- removed wrappers: `market_state_engine/{app,contracts,routes,errors,msl}.py`
- guard/test imports switched to `services.market_state_engine.src.*`

2.14 `market_state_engine` decommission batch-b (phase-1)
- removed wrappers: `market_state_engine/adapters/**/*.py`, `market_state_engine/ports/**/*.py`
- consumer tests switched to `services.market_state_engine.src.adapters.*`

2.15 `market_state_engine` decommission batch-c (phase-1)
- removed wrappers: `market_state_engine/factors/**/*.py`, `market_state_engine/state_inference/**/*.py`
- state_inference tests switched to `services.market_state_engine.src.state_inference.*`

2.16 `market_state_engine` decommission batch-d (phase-1)
- removed wrappers: `market_state_engine/{__init__,main,service,engine}.py`
- all state-layer tests switched to `services.market_state_engine.src.*`

3. `execution_service/main.py`
- migrated impl: `services/execution_service/runtime/main.py`
- legacy wrapper status: removed in 28 (decommission batch-a phase-1)

4. `event_center_new/main.py`
- migrated impl: `services/event_center_new/runtime/main.py`
- legacy wrapper status: removed in 26 (decommission batch-a phase-1)

5. `event_center_new/replay_main.py`
- migrated impl: `services/event_center_new/runtime/replay_main.py`
- legacy wrapper status: removed in 26 (decommission batch-a phase-1)

6. `agent_server_new/runner.py`
- migrated impl: `services/agent_server_new/runtime/runner.py`
- legacy wrapper status: removed in 27 (decommission batch-a phase-1)

7. `agent_server_new/pipeline_smoke.py`
- migrated impl: `services/agent_server_new/runtime/pipeline_smoke.py`
- legacy wrapper status: removed in 27 (decommission batch-a phase-1)

8. `agent_server_new/memory_summary_runner.py`
- migrated impl: `services/agent_server_new/runtime/memory_summary_runner.py`
- legacy wrapper status: removed in 27 (decommission batch-a phase-1)

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

1. 服务入口兼容壳已清理完成，当前风险转向“文档与脚本命令是否完全与 `services.*` 对齐”。
2. 少量历史文档仍保留迁移过程描述，可能造成“当前状态与历史节点”混淆。
3. workflow/snapshot/text-wiring 仍有 `scripts/*` 硬绑定，后续建议继续收敛到 `tools/*`。

## 5. 下一阶段建议

1. 进入 Phase-3.5：收敛 `scripts/*` 到 `tools/*` 并逐步下线脚本兼容层。
2. 为 `event_center_new / agent_server_new / execution_service` 增加与 `feature_service`、`market_state_engine` 同等级别的“compat decommission”文档归档。
3. 在 CI 中新增“命令入口一致性守卫”，防止文档回归到已下线的旧模块入口。
