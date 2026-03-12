# execution_service Migration

更新时间：2026-03-11

## 目标

将执行层文档维持为“当前生效版本”，避免历史版本信息混入联调入口。

## 当前基线（Latest Only）

1. API 入口：`services/execution_service/docs/api.md`
2. 契约映射版本：`execution-schema-mapping-v15`
3. 核心输入契约：`decision_intent.schema.json`
4. 核心输出契约：`execution_result.schema.json`
5. 对账输出契约：`execution_reconcile_result.schema.json`
6. 状态契约：`decision_state.schema.json`
7. 契约索引单入口：`docs/CONTRACT_INDEX.md`

## 已完成（当前有效能力）

1. 执行裁决主链路稳定：`POST /internal/execution/decide`
2. 回执对账链路可用：`POST /internal/execution/reconcile`
3. `decision_confidence` 已为主字段，`confidence` 仅保留兼容镜像
4. `order_result`/`reconcile_result` 已收敛为白名单结构
5. 共享 schema 已拆分并通过 `$ref` 复用（confidence/enums/io payload 等）
6. `schema_mapping_version` 与 `/version`、`CONTRACT_INDEX` 已守卫对齐

## 文档维护规则

1. 本文件只保留“当前基线 + 进行中事项”，不再记录历史流水号
2. 历史版本明细统一以 Git 提交记录追溯
3. 发生 breaking 变更时，仅更新当前基线版本与对应迁移动作

## 进行中事项

1. 持续将执行层风险规则与状态字段语义收敛到 schema 单一来源
2. 增加更多跨服务契约联调用例（agent -> execution -> reconcile）
3. 逐步替换 stub 数据提供器为生产级 provider（按环境开关）

## 归档待办（未启用）

1. memory summary 入库归档能力暂不落地
2. 已在文档中保留建议库表结构，后续单独立项创建
