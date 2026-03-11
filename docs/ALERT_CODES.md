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
