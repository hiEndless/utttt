# routes.py 模块说明

## 路径

- canonical：`services/feature_service/src/routes.py`
- 兼容壳：`feature_service/routes.py`


## 功能作用

`routes.py` 负责 HTTP 协议层处理，核心职责：

- 参数校验：`exchange`、`symbol` 必填
- 错误映射：`FeatureDataUnavailableError` -> HTTP 503 标准错误体
- 响应封装：统一 `meta + data` 契约

当前暴露接口：

- `GET /internal/feature-service/healthz`
- `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`
- `GET /internal/feature-service/features/{exchange}/{symbol}`

## 输入输出

- 输入：HTTP 请求、`FeatureService` 返回的数据
- 输出：契约化响应（`FeatureResponse` / `RawStructureResponse`）

## 关键价值

- 统一服务对外行为（状态码、错误码、响应结构）
- 屏蔽 service 内部实现细节，降低下游耦合

## 迭代方向建议

1. 增加请求级 trace_id 透传（header -> response meta -> 日志）。
2. 将参数校验迁移到显式类型约束（枚举/正则），减少手写判断分散。
3. 对 503 场景补充 `retry_after_ms` 或推荐重试策略字段。
