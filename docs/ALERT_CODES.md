# 告警码清单（新架构）

更新时间：2026-03-11

目标：统一线上日志告警口径，避免同类问题在不同服务中使用不同命名。

## 命名规则

- 统一前缀：`<SERVICE>_<DOMAIN>_<ISSUE>`
- 全大写下划线分隔
- 必须稳定，不随文案变化

## 已冻结告警码

| code | service | owner | introduced_in | lifecycle | trigger | signals |
|---|---|---|---|---|---|---|
| `MSE_SELECTED_EVENTS_UNVERSIONED` | `market_state_engine` | `state-layer` | `market_state_engine@c8f322e` | `active` | 接收到 selected_event 但缺失 `trace.schema_version` | `anomaly_flags` 包含 `selected_events_unversioned`；`state_features.evidence.selected_events_unversioned_count > 0` |

处理建议：
- 检查 `event_center_new/docs/selected_event.schema.json` 是否被破坏
- 检查上游 selected_event 生产链路是否遗漏 trace 透传

## 维护约定

1. 新增告警码时，必须填写：`owner / introduced_in / lifecycle`。
2. 告警码废弃时，不直接删除；`lifecycle` 改为 `deprecated` 并保留迁移窗口说明。
3. CI 失败码（如脚本 `FAIL_CODE=...`）不放在本文件，继续由各守卫脚本 `--help` 文档维护。

## 生命周期规则

状态枚举：
- `active`：正常生效，允许触发与告警。
- `deprecated`：进入废弃窗口，保留兼容与观测，不再推荐新增依赖。
- `removed`：已下线，不应继续出现在运行时日志中。

状态转换（单向）：
- `active -> deprecated -> removed`
- 禁止 `deprecated -> active` 回滚（如需恢复，应新增告警码并记录原因）。

最短保留周期：
- `deprecated` 阶段至少保留 14 天，且跨过 1 个完整发布窗口后，才能进入 `removed`。

记录要求：
- 进入 `deprecated` 时，必须补充迁移说明（替代告警码、影响范围、计划移除时间）。
- 进入 `removed` 时，必须保留历史记录（可在本文件追加“removed 历史”条目，禁止直接删痕）。
