# main.py 模块说明

## 路径

- canonical：`services/feature_service/runtime/main.py`
- 兼容壳：`feature_service/main.py`


## 功能作用

`main.py` 是进程启动入口，负责读取环境变量并启动 Uvicorn：

- `FEATURE_SERVICE_LOG_LEVEL`
- `FEATURE_SERVICE_HOST`
- `FEATURE_SERVICE_PORT`

## 输入输出

- 输入：环境变量、`create_app()` 返回的 app
- 输出：启动 HTTP 服务进程

## 关键价值

- 将部署参数外置，支持本地/测试/生产差异化启动
- 将运行入口与应用装配分离，便于 `import app` 方式运行

## 迭代方向建议

1. 增加环境变量合法性校验（端口范围、log level 白名单）。
2. 为容器部署补充默认 worker/timeout 配置策略文档。
3. 增加标准化启动日志（host/port/schema version/provider mode）。
