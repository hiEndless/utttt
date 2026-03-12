# app.py 模块说明

## 路径

- canonical：`services/feature_service/src/app.py`
- 兼容壳：`feature_service/app.py`


## 功能作用

`app.py` 负责创建 FastAPI 应用实例，并完成 `FeatureService` 的默认装配。

当前实现路径是单一路径：

- 通过 `build_independent_provider_bundle()` 构建 provider 组合
- 通过 `FeatureService.from_bundle(...)` 创建服务实例
- 挂载 `create_router(service)` 暴露 API

## 输入输出

- 输入：运行时环境（Python 进程、依赖可用性）
- 输出：`FastAPI` app 对象

## 关键价值

- 固定唯一装配路径，避免多模式配置漂移
- 将组装逻辑与业务逻辑解耦，便于测试和替换 provider

## 迭代方向建议

1. 增加启动期自检（Redis 可达、关键 provider 可初始化）并输出结构化日志。
2. 增加应用级依赖注入钩子，支持测试环境显式传入 bundle（而不是仅走默认构建）。
3. 增加版本与构建信息端点（例如 `/healthz` 扩展 build sha、schema version）。
