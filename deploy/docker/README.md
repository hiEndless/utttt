# Docker 部署（api + agent_server）

## 文件
- `deploy/docker/Dockerfile`：通用 Python 镜像构建（安装 requirements.txt 并复制代码）
- `deploy/docker/docker-compose.yml`：启动 redis、api、agent_server

## 使用
在仓库根目录执行：

```bash
docker compose -f deploy/docker/docker-compose.yml up --build
```

## 说明
- `agent_server` 默认走服务内 gating：未开启或未就绪时空转待命（不消费/不跑 cron/不调用 LLM）
- 运行态可在前端概览页查看，或通过 `GET /api/agent/status` 查询

