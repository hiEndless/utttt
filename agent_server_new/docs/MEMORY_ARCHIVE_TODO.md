# Symbol Memory DB 归档代办（暂不实现）

更新时间：2026-03-10

当前决策：`memory summary` **暂不落 DB**，先保留在 Redis/In-Memory + 文档方案，后续再创建归档工程。

## 1. 代办范围

1. 新增 `symbol_memory_summary_archive` 持久化表（用于审计与复盘）。
2. 新增 `symbol_memory_raw_archive` 持久化表（用于重放与差分分析）。
3. 新增归档任务（按 symbol 定时写入快照，不影响实时决策路径）。

## 2. 建议库表结构（PostgreSQL）

## 2.1 `symbol_memory_summary_archive`

建议字段：

1. `id` `bigserial` PK
2. `exchange` `varchar(32)` not null
3. `symbol` `varchar(64)` not null
4. `summary_ts` `bigint` not null
5. `event_count` `int` not null default 0
6. `trend_bias` `varchar(16)` not null default 'neutral'
7. `signal_direction_count` `jsonb` not null
8. `signal_verdict_count` `jsonb` not null
9. `plan_action_count` `jsonb` not null
10. `last_event_id` `varchar(128)` null
11. `last_plan_action` `varchar(32)` not null default 'hold'
12. `summary_payload` `jsonb` not null
13. `schema_version` `int` not null default 1
14. `created_at` `timestamptz` not null default now()

建议索引：

1. `idx_smsa_exchange_symbol_ts` on `(exchange, symbol, summary_ts desc)`
2. `idx_smsa_created_at` on `(created_at desc)`

## 2.2 `symbol_memory_raw_archive`

建议字段：

1. `id` `bigserial` PK
2. `exchange` `varchar(32)` not null
3. `symbol` `varchar(64)` not null
4. `event_id` `varchar(128)` not null
5. `event_ts` `bigint` not null
6. `signal_direction` `varchar(16)` null
7. `signal_verdict` `varchar(32)` null
8. `plan_action` `varchar(32)` null
9. `plan_direction` `varchar(16)` null
10. `raw_payload` `jsonb` not null
11. `schema_version` `int` not null default 1
12. `created_at` `timestamptz` not null default now()

建议索引：

1. `uq_smra_exchange_symbol_event_id` unique `(exchange, symbol, event_id)`
2. `idx_smra_exchange_symbol_ts` on `(exchange, symbol, event_ts desc)`
3. `idx_smra_created_at` on `(created_at desc)`

## 3. 归档写入策略建议

1. 实时链路只写 Redis，不直写 DB（避免增加决策延迟）。
2. 后台任务按 `N` 分钟批量写 DB：
- 先拉取最近 `summary/raw`
- 幂等写入（按 unique key 去重）
- 打点归档成功率与延迟
3. DB 归档失败不阻塞实时决策（降级为告警）。

## 4. 保留周期建议

1. `raw_archive`：30~90 天（视存储成本）
2. `summary_archive`：180~365 天（用于策略复盘）
3. 通过分区表（按月）控制归档与清理成本

## 5. 实施前置检查清单

1. 确认最终 DB 选型（PostgreSQL/MySQL）
2. 确认跨环境 schema 迁移方案（Alembic/Flyway）
3. 确认 `schema_version` 升级策略
4. 确认 replay 查询最小 API（按 symbol + 时间窗口）
