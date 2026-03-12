# Verification API Draft (Read-only)

更新时间：2026-03-13
状态：draft-v1（最小文件后端实现已落地）

## 1. 目标

为 `verification` 结果提供统一只读查询面，便于后续接入 dashboard/告警系统。

## 2. 基础约定

- Base path: `/internal/verification`
- 返回格式：`application/json`
- 时间字段：`*_at_ms`（毫秒）
- 当前报告 schema：`verification-report-v1`
- 聚合 schema：`verification-report-aggregate-v1`

## 3. 接口草案

### 3.1 获取最新 suite 报告

`GET /internal/verification/reports/latest?suite={suite}`

响应示例：

```json
{
  "schema_version": "verification-report-v1",
  "suite": "quick",
  "status": "passed",
  "exit_code": 0,
  "started_at_ms": 1773263320000,
  "finished_at_ms": 1773263320787,
  "duration_ms": 787,
  "guards": [
    {"name": "contract_docs_index", "status": "passed", "duration_ms": 120}
  ]
}
```

### 3.2 获取报告列表

`GET /internal/verification/reports?suite={suite}&status={passed|failed}&limit={n}`

响应示例：

```json
{
  "items": [
    {"suite": "quick", "status": "passed", "finished_at_ms": 1773263320787}
  ],
  "count": 1
}
```

### 3.3 获取聚合摘要

`GET /internal/verification/reports/summary?window_hours={n}&suite={suite}`

响应示例：

```json
{
  "schema_version": "verification-report-aggregate-v1",
  "report_count": 12,
  "passed": 11,
  "failed": 1,
  "pass_rate": 0.916667,
  "avg_duration_ms": 4021,
  "latest_finished_at_ms": 1773263320787,
  "suites": [
    {"suite": "quick", "count": 8, "passed": 8, "failed": 0, "avg_duration_ms": 3150, "latest_finished_at_ms": 1773263320787}
  ],
  "memory_alert_code_count": 1,
  "memory_top_alert_codes": [
    {
      "alert_code": "AGENT_ALTERNATIVE_SOURCES_CONFLICT",
      "count": 2,
      "symbols": ["binance:ETHUSDT", "binance:BTCUSDT"],
      "symbol_count": 2
    }
  ]
}
```

### 3.4 获取单次报告原文

`GET /internal/verification/reports/{report_id}`

- `report_id` 可映射到落盘文件名（后续可升级到 DB 主键）。

## 4. 鉴权与权限建议

- 默认仅内网可访问。
- 生产环境必须启用只读鉴权（token 或 service account）。
- 不提供写接口；写入仍由 CI/工具链落盘。

## 4.1 Debug/Guard 校验开关

- 环境变量：`VERIFICATION_API_VALIDATE_SUMMARY_SCHEMA=1`
- 作用：对 `/internal/verification/reports/summary` 响应执行 `verification_report_aggregate_v1` schema 运行时校验
- 默认：关闭（`0`）
- 建议：在 debug/guard 环境开启，生产默认关闭以避免额外开销

## 5. 分阶段实现建议

1. 文件后端：从 `verification/reports/*.json` 读取。
2. 增加聚合缓存：按 suite/window 预计算 summary。
3. 再引入 DB/TSDB 作为历史归档层。

## 6. 非目标

- 不在本阶段实现告警投递。
- 不在本阶段替换现有脚本执行链。

## 7. 当前实现位置（最小版）

- API 应用：`verification/api/app.py`
- 启动入口：`python3 -m verification.api.main`
- 本地脚本：`tools/local/run_verification_api.sh`
- 单测：`verification/text/test_verification_api.py`
